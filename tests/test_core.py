from __future__ import annotations

import copy
import hashlib
import hmac
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from palate import config, contracts, db
from palate.chat import photon, session
from palate.chat import replan as chat_replan
from palate.enrich import knowledge_base
from palate.ingest import extract, gmail_sync, prefilter
from palate.plan import candidates, places
from palate.plan.assemble import build_itinerary, replan, swap_stop
from palate.profile.build import build_profile


class DatabaseCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self._old_db_path = config.DB_PATH
        self._old_places_key = config.GOOGLE_PLACES_API_KEY
        config.DB_PATH = Path(self._temp.name) / "palate-test.db"
        config.GOOGLE_PLACES_API_KEY = ""
        db.migrate()

    def tearDown(self) -> None:
        config.DB_PATH = self._old_db_path
        config.GOOGLE_PLACES_API_KEY = self._old_places_key
        self._temp.cleanup()

    @staticmethod
    def profile() -> dict:
        return {
            "home_city": "San Francisco",
            "earliest_activity_hour": 11,
            "peak_dining_hour": 20,
            "preferred_days": ["Wed"],
            "typical_party_size": 2,
            "price_ceiling": 3,
            "cancellation_threshold": 4,
            "revisit_ratio": 1.9,
            "novelty_appetite": "low",
            "cuisine_affinity": {"italian": 0.5, "portuguese": 0.4},
            "cuisine_aversion": ["sushi"],
            "booking_lead_time_median_days": 6,
            "seat_preference": "bar",
            "pace": 2.4,
            "avoided_categories": [],
            "aspiration_gap": [],
            "most_repeated": [{"name": "Cotogna", "visits": 4}],
            "computed_at": "test",
            "evidence": {
                "earliest_activity_hour": {"n": 2, "of": 20, "note": ""},
                "peak_dining_hour": {"n": 12, "of": 20, "note": ""},
                "typical_party_size": {"n": 15, "of": 20, "note": ""},
                "cancellation_threshold": {"n": 4, "of": 4, "note": ""},
                "revisit_ratio": {"n": 22, "of": 13, "note": ""},
                "seat_preference": {"n": 8, "of": 10, "note": ""},
            },
        }


class CandidateTests(unittest.TestCase):
    def test_filters_distaste_before_ranking_and_never_uses_rating(self) -> None:
        profile = {
            "cancellation_threshold": 4,
            "cuisine_aversion": ["sushi"],
            "avoided_categories": ["event"],
            "cuisine_affinity": {"italian": 0.8},
            "price_ceiling": 3,
        }
        pool = [
            {
                "name": "Popular Sushi",
                "category": "restaurant",
                "cuisine": ["sushi"],
                "price_band": 2,
                "rating": 5.0,
            },
            {
                "name": "Repeat-shaped",
                "category": "restaurant",
                "cuisine": ["italian"],
                "price_band": 3,
                "rating": 1.0,
            },
            {
                "name": "Cancellation band",
                "category": "restaurant",
                "cuisine": ["italian"],
                "price_band": 4,
                "rating": 5.0,
            },
        ]
        filtered = candidates.filter_by_profile(pool, profile)
        self.assertEqual([item["name"] for item in filtered], ["Repeat-shaped"])

        first = candidates.rank(
            [
                {"name": "A", "category": "restaurant", "price_band": 3, "rating": 1},
                {"name": "B", "category": "restaurant", "price_band": 3, "rating": 5},
            ],
            profile,
        )
        second = candidates.rank(
            [
                {"name": "A", "category": "restaurant", "price_band": 3, "rating": 5},
                {"name": "B", "category": "restaurant", "price_band": 3, "rating": 1},
            ],
            profile,
        )
        self.assertEqual(
            [item["name"] for item in first], [item["name"] for item in second]
        )


class PlaceTests(DatabaseCase):
    def test_text_search_is_normalized_and_cached(self) -> None:
        config.GOOGLE_PLACES_API_KEY = "test-key"
        payload = {
            "places": [
                {
                    "id": "place-1",
                    "displayName": {"text": "Small Table"},
                    "primaryType": "italian_restaurant",
                    "types": ["restaurant"],
                    "priceLevel": "PRICE_LEVEL_MODERATE",
                    "rating": 4.7,
                    "userRatingCount": 123,
                    "location": {"latitude": 1.2, "longitude": 3.4},
                }
            ]
        }
        with mock.patch.object(places, "_request", return_value=payload) as request:
            first = places.search("Small Table", "Lisbon")
            second = places.search("Small Table", "Lisbon")
        self.assertEqual(first, second)
        self.assertEqual(first["price_band"], 2)
        self.assertEqual(first["cuisine"], ["italian"])
        request.assert_called_once()


class ItineraryTests(DatabaseCase):
    def test_build_swap_and_replan_hold_contract(self) -> None:
        profile = self.profile()
        itinerary = build_itinerary(profile, "Lisbon", days=2)
        self.assertEqual(contracts.validate_itinerary(itinerary, profile), [])

        original = copy.deepcopy(itinerary)
        stops = [stop for _, stop in contracts.iter_stops(itinerary)]
        target = stops[1]
        swapped = swap_stop(itinerary, target["id"], reason="test")
        self.assertEqual(itinerary, original)
        old_by_id = {stop["id"]: stop for _, stop in contracts.iter_stops(original)}
        new_by_id = {stop["id"]: stop for _, stop in contracts.iter_stops(swapped)}
        self.assertNotIn(target["id"], new_by_id)
        for stop_id, stop in old_by_id.items():
            if stop_id != target["id"]:
                self.assertEqual(new_by_id[stop_id], stop)

        first = next(contracts.iter_stops(swapped))[1]
        first["locked"] = True
        locked = copy.deepcopy(first)
        before = copy.deepcopy(swapped)
        changed = replan(
            swapped,
            f"{swapped['days'][0]['date']}T00:00",
            "it is raining",
        )
        self.assertEqual(swapped, before)
        self.assertEqual(
            next(
                stop
                for _, stop in contracts.iter_stops(changed)
                if stop["id"] == locked["id"]
            ),
            locked,
        )
        changed_stops = [
            stop
            for _, stop in contracts.iter_stops(changed)
            if stop["id"] != locked["id"]
            and str(stop.get("because") or "").startswith("Rain plan:")
        ]
        self.assertTrue(changed_stops, "rain must visibly change an unlocked future stop")
        self.assertEqual(contracts.validate_itinerary(changed), [])

    def test_avoided_category_is_never_reintroduced(self) -> None:
        profile = self.profile()
        profile["avoided_categories"] = ["activity"]
        itinerary = build_itinerary(profile, "Lisbon", days=1)
        categories = {stop["category"] for _, stop in contracts.iter_stops(itinerary)}
        self.assertNotIn("activity", categories)


class IngestTests(DatabaseCase):
    def test_calendar_rows_keep_their_source(self) -> None:
        db.execute(
            "INSERT INTO raw_message"
            " (id,source,subject,body,received_at,matched_vendor,extracted,fetched_at)"
            " VALUES (?,?,?,?,?,?,0,?)",
            (
                "calendar:event-1",
                "calendar",
                "Dinner at Prado",
                "Location: Prado\nStart: 2026-08-01T20:00:00+01:00",
                "2026-08-01T20:00:00+01:00",
                "calendar",
                db.now(),
            ),
        )
        result = {
            "visits": [
                {
                    "source_ref": "calendar:event-1",
                    "vendor": "calendar",
                    "place_name_raw": "Prado",
                    "city": "Lisbon",
                    "category": "restaurant",
                    "cuisine": None,
                    "price_band": None,
                    "party_size": None,
                    "scheduled_at": "2026-08-01T20:00",
                    "booked_at": None,
                    "status": "confirmed",
                    "cancelled_at": None,
                    "seat": None,
                    "raw_total_cents": None,
                }
            ]
        }
        with mock.patch("palate.ingest.extract.llm.complete_json", return_value=result):
            self.assertEqual(extract.extract_pending(), 1)
        row = db.one("SELECT source,vendor,is_travel FROM visit")
        self.assertEqual(row["source"], "calendar")
        self.assertIsNone(row["vendor"])
        self.assertEqual(row["is_travel"], 1)
        raw = db.one(
            "SELECT extracted,sender,subject,body FROM raw_message"
            " WHERE id='calendar:event-1'"
        )
        self.assertEqual(raw["extracted"], 1)
        self.assertIsNone(raw["sender"])
        self.assertIsNone(raw["subject"])
        self.assertIsNone(raw["body"])

    def test_prefilter_discards_unmatched_private_text(self) -> None:
        db.execute(
            "INSERT INTO raw_message"
            " (id,source,sender,subject,body,received_at,extracted,fetched_at)"
            " VALUES (?,?,?,?,?,?,0,?)",
            (
                "personal-1",
                "gmail",
                "friend@example.com",
                "Weekend plans",
                "Private conversation",
                db.now(),
                db.now(),
            ),
        )
        self.assertEqual(prefilter.run(), {})
        row = db.one(
            "SELECT extracted,sender,subject,body FROM raw_message"
            " WHERE id='personal-1'"
        )
        self.assertEqual(row["extracted"], 1)
        self.assertIsNone(row["sender"])
        self.assertIsNone(row["subject"])
        self.assertIsNone(row["body"])

    def test_gmail_resync_does_not_restore_discarded_text(self) -> None:
        db.execute(
            "INSERT INTO raw_message"
            " (id,source,received_at,extracted,fetched_at)"
            " VALUES (?,?,?,?,?)",
            ("message-1", "gmail", db.now(), 1, db.now()),
        )
        api = mock.MagicMock()
        api.list.return_value.execute.return_value = {
            "messages": [{"id": "message-1"}]
        }
        api.get.return_value.execute.return_value = {
            "id": "message-1",
            "internalDate": "1785000000000",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "From", "value": "updates@resy.com"},
                    {"name": "Subject", "value": "Your booking"},
                ],
                "body": {"data": "U2Vuc2l0aXZlIGJvZHk="},
            },
        }
        service = mock.MagicMock()
        service.users.return_value.messages.return_value = api
        with mock.patch.object(gmail_sync, "gmail_service", return_value=service):
            self.assertEqual(gmail_sync.run_sync(limit=1), 1)
        row = db.one(
            "SELECT extracted,sender,subject,body FROM raw_message"
            " WHERE id='message-1'"
        )
        self.assertEqual(row["extracted"], 1)
        self.assertIsNone(row["sender"])
        self.assertIsNone(row["subject"])
        self.assertIsNone(row["body"])

    def test_dedupe_keeps_cancellation_and_fills_richer_fields(self) -> None:
        base = {
            "source": "gmail",
            "vendor": "resy",
            "place_name_raw": "Cotogna",
            "place_id": None,
            "city": "San Francisco",
            "category": "restaurant",
            "cuisine": ["italian"],
            "price_band": 3,
            "party_size": 2,
            "scheduled_at": "2026-08-01T20:00",
            "booked_at": "2026-07-20T10:00",
            "cancelled_at": None,
            "is_travel": 0,
            "intent_only": 0,
            "seat": "bar",
            "raw_total_cents": None,
            "created_at": "2026-07-20T10:00",
        }
        confirmed = {**base, "id": "one", "source_ref": "one", "status": "confirmed"}
        cancelled = {
            **base,
            "id": "two",
            "source_ref": "two",
            "status": "cancelled",
            "party_size": None,
            "seat": None,
            "cancelled_at": "2026-07-31T22:00",
            "created_at": "2026-07-31T22:00",
        }
        db.upsert_visit(confirmed)
        db.upsert_visit(cancelled)
        self.assertEqual(extract.dedupe_visits(), 1)
        row = db.one("SELECT status,party_size,seat FROM visit")
        self.assertEqual(
            dict(row), {"status": "cancelled", "party_size": 2, "seat": "bar"}
        )


class ChatTests(DatabaseCase):
    def test_full_send_begins_with_the_source_backed_profile(self) -> None:
        db.seed()
        build_profile()
        sent_text: list[str] = []

        def fake_send(phone: str, text: str) -> str:
            sent_text.append(text)
            return f"message-{len(sent_text)}"

        with mock.patch("palate.chat.replan.photon.send", side_effect=fake_send):
            message_ids = chat_replan.send_full_itinerary(
                "+15551234567", "Lisbon", days=1
            )

        self.assertEqual(len(message_ids), len(sent_text))
        self.assertIn("You book Wednesdays", sent_text[0])
        self.assertTrue(any("Skip Pastéis de Belém" in text for text in sent_text))
        saved = session.get_session("+15551234567")
        self.assertIsNotNone(saved["itinerary"])
        self.assertEqual(
            len(saved["state"]["message_map"]),
            sum(len(day["stops"]) for day in saved["itinerary"]["days"]),
        )

    def test_signature_and_payload_normalization(self) -> None:
        secret = "secret"
        old_secret = config.PHOTON_WEBHOOK_SECRET
        config.PHOTON_WEBHOOK_SECRET = secret
        self.addCleanup(setattr, config, "PHOTON_WEBHOOK_SECRET", old_secret)
        body = json.dumps(
            {
                "event": "messages",
                "message": {
                    "id": "msg-1",
                    "direction": "inbound",
                    "space": {"id": "space-1"},
                    "sender": {"id": "+15551234567"},
                    "content": {"type": "text", "text": "it's raining"},
                },
            },
            separators=(",", ":"),
        ).encode()
        timestamp = str(int(time.time()))
        signature = (
            "v0="
            + hmac.new(
                secret.encode(),
                b"v0:" + timestamp.encode() + b":" + body,
                hashlib.sha256,
            ).hexdigest()
        )
        headers = {
            "X-Spectrum-Timestamp": timestamp,
            "X-Spectrum-Signature": signature,
        }
        self.assertTrue(photon.verify(body, headers))
        event = photon.parse_inbound(json.loads(body), headers)
        self.assertEqual(
            event,
            {"kind": "text", "from": "+15551234567", "text": "it's raining"},
        )

    def test_tapback_swaps_one_stop_and_persists_new_mapping(self) -> None:
        itinerary = build_itinerary(self.profile(), "Lisbon", days=1)
        phone = "+15551234567"
        target = [stop for _, stop in contracts.iter_stops(itinerary)][1]
        session.save_session(phone, itinerary)
        session.map_message(phone, "old-message", target["id"])
        with mock.patch.object(photon, "send", return_value="new-message"):
            self.assertEqual(
                chat_replan.handle_tapback(phone, "old-message", "down"),
                [],
            )
        updated = session.get_session(phone)["itinerary"]
        updated_ids = {stop["id"] for _, stop in contracts.iter_stops(updated)}
        self.assertNotIn(target["id"], updated_ids)
        self.assertIn(session.stop_for_message(phone, "new-message"), updated_ids)


class EnrichmentTests(DatabaseCase):
    def test_only_restaurant_shaped_lists_clear_precision_gate(self) -> None:
        content = "\n".join(f"- Place {index}" for index in range(1, 6))
        self.assertEqual(
            len(
                knowledge_base._items(
                    {"title": "Restaurants to try", "content": content}
                )
            ),
            5,
        )
        self.assertEqual(
            knowledge_base._items({"title": "Work tasks", "content": content}),
            [],
        )

    def test_notion_article_body_is_downloaded_without_merge_headers(self) -> None:
        content = "\n".join(f"- Place {index}" for index in range(1, 6))
        response = mock.Mock()
        response.content = json.dumps({"blocks": [{"text": content}]}).encode()
        response.raise_for_status.return_value = None
        with mock.patch.object(
            knowledge_base.httpx, "get", return_value=response
        ) as request:
            downloaded = knowledge_base._download_content(
                {
                    "article_content_download_url": (
                        "https://example-bucket.s3.amazonaws.com/article?signature=x"
                    )
                }
            )
        self.assertEqual(downloaded, {"blocks": [{"text": content}]})
        _, kwargs = request.call_args
        self.assertNotIn("headers", kwargs)
        self.assertFalse(kwargs["follow_redirects"])

    def test_notion_sync_hydrates_article_and_writes_intent_rows(self) -> None:
        content = "\n".join(f"- Place {index}" for index in range(1, 6))
        article = {
            "id": "article-1",
            "title": "Restaurants to try",
            "article_content_download_url": "https://example.com/article",
            "created_at": "2026-07-26T10:00:00Z",
        }
        with (
            mock.patch.object(knowledge_base, "_pages", return_value=[article]),
            mock.patch.object(
                knowledge_base, "_download_content", return_value=content
            ),
        ):
            self.assertEqual(knowledge_base.sync(), 5)
        self.assertEqual(
            db.one("SELECT COUNT(*) AS n FROM visit WHERE intent_only=1")["n"],
            5,
        )


class ConfigTests(unittest.TestCase):
    def test_configured_paths_preserve_absolute_values(self) -> None:
        absolute = Path(tempfile.gettempdir()) / "palate-absolute.db"
        self.assertEqual(config.resolve_path(str(absolute)), absolute)
        self.assertEqual(
            config.resolve_path("data/palate.db"),
            config.ROOT / "data/palate.db",
        )


if __name__ == "__main__":
    unittest.main()
