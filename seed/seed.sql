-- Seed visits. BASE.
-- Purpose: B, C, and D can build and demo before A's live pipeline lands, and
-- this is the fallback dataset if the 1:00 AM real-inbox gate fails (PRD 7).
--
-- Shaped to exercise every profile metric: a late-evening Tue/Wed diner, party
-- of two, bar seats, heavy repeat visits, a hard cancel pattern above band 4,
-- one abandoned early-morning tour, and a Notion aspiration gap.

DELETE FROM visit WHERE source_ref LIKE 'seed-%';

INSERT OR REPLACE INTO visit
 (id, source, source_ref, vendor, place_name_raw, place_id, city, category, cuisine,
  price_band, party_size, scheduled_at, booked_at, status, cancelled_at, is_travel,
  intent_only, seat, raw_total_cents, created_at)
VALUES
 ('seed01','gmail','seed-1','resy','Cotogna',NULL,'San Francisco','restaurant','["italian"]',3,2,'2026-01-14T20:45','2026-01-08T11:02','confirmed',NULL,0,0,'bar',18400,'2026-07-25T18:00'),
 ('seed02','gmail','seed-2','resy','Cotogna',NULL,'San Francisco','restaurant','["italian"]',3,2,'2026-02-11T20:30','2026-02-05T09:30','confirmed',NULL,0,0,'bar',17600,'2026-07-25T18:00'),
 ('seed03','gmail','seed-3','resy','Cotogna',NULL,'San Francisco','restaurant','["italian"]',3,2,'2026-03-18T21:00','2026-03-12T14:20','confirmed',NULL,0,0,'bar',19100,'2026-07-25T18:00'),
 ('seed04','gmail','seed-4','resy','Cotogna',NULL,'San Francisco','restaurant','["italian"]',3,2,'2026-05-06T20:45','2026-04-29T10:11','confirmed',NULL,0,0,'bar',18800,'2026-07-25T18:00'),
 ('seed05','gmail','seed-5','tock','Rich Table',NULL,'San Francisco','restaurant','["californian"]',3,2,'2026-01-28T20:30','2026-01-20T08:45','confirmed',NULL,0,0,'table',21200,'2026-07-25T18:00'),
 ('seed06','gmail','seed-6','tock','Rich Table',NULL,'San Francisco','restaurant','["californian"]',3,2,'2026-04-15T20:45','2026-04-07T19:02','confirmed',NULL,0,0,'table',20400,'2026-07-25T18:00'),
 ('seed07','gmail','seed-7','opentable','Zuni Cafe',NULL,'San Francisco','restaurant','["californian"]',2,2,'2026-02-25T20:15','2026-02-21T12:40','confirmed',NULL,0,0,'bar',13100,'2026-07-25T18:00'),
 ('seed08','gmail','seed-8','opentable','Zuni Cafe',NULL,'San Francisco','restaurant','["californian"]',2,2,'2026-03-25T20:30','2026-03-19T16:05','confirmed',NULL,0,0,'bar',12800,'2026-07-25T18:00'),
 ('seed09','gmail','seed-9','opentable','Zuni Cafe',NULL,'San Francisco','restaurant','["californian"]',2,2,'2026-06-10T21:00','2026-06-03T18:22','confirmed',NULL,0,0,'bar',14000,'2026-07-25T18:00'),
 ('seed10','gmail','seed-10','resy','Bar Crenn',NULL,'San Francisco','bar','["french"]',3,2,'2026-05-20T21:30','2026-05-14T13:00','confirmed',NULL,0,0,'bar',16200,'2026-07-25T18:00'),
 ('seed11','gmail','seed-11','resy','Bar Crenn',NULL,'San Francisco','bar','["french"]',3,2,'2026-06-24T21:15','2026-06-17T09:14','confirmed',NULL,0,0,'bar',15800,'2026-07-25T18:00'),
 ('seed12','gmail','seed-12','tock','Nari',NULL,'San Francisco','restaurant','["thai"]',2,2,'2026-01-21T20:30','2026-01-15T10:00','confirmed',NULL,0,0,'table',11200,'2026-07-25T18:00'),
 ('seed13','gmail','seed-13','tock','Nari',NULL,'San Francisco','restaurant','["thai"]',2,2,'2026-04-01T20:45','2026-03-26T11:30','confirmed',NULL,0,0,'table',11800,'2026-07-25T18:00'),
 -- tried once, never returned: the cuisine_aversion signal
 ('seed14','gmail','seed-14','opentable','Kusakabe',NULL,'San Francisco','restaurant','["sushi"]',4,2,'2026-02-04T20:00','2026-01-28T15:45','confirmed',NULL,0,0,'table',31000,'2026-07-25T18:00'),
 -- the cancellation pattern: everything at band 4 gets killed
 ('seed15','gmail','seed-15','tock','Californios',NULL,'San Francisco','restaurant','["mexican"]',4,2,'2026-03-05T20:00','2026-02-20T09:00','cancelled','2026-03-04T22:10',0,0,'table',NULL,'2026-07-25T18:00'),
 ('seed16','gmail','seed-16','tock','Benu',NULL,'San Francisco','restaurant','["californian"]',4,2,'2026-04-22T19:30','2026-04-02T08:30','cancelled','2026-04-21T23:40',0,0,'table',NULL,'2026-07-25T18:00'),
 ('seed17','gmail','seed-17','resy','Angler',NULL,'San Francisco','restaurant','["seafood"]',4,2,'2026-05-28T20:00','2026-05-14T17:15','cancelled','2026-05-27T21:05',0,0,'table',NULL,'2026-07-25T18:00'),
 ('seed18','gmail','seed-18','tock','Quince',NULL,'San Francisco','restaurant','["italian"]',4,2,'2026-06-30T19:45','2026-06-12T12:00','cancelled','2026-06-29T22:55',0,0,'table',NULL,'2026-07-25T18:00'),
 -- travel: Mexico City, plus the 9am tour cancelled the night before
 ('seed19','gmail','seed-19','resy','Contramar',NULL,'Mexico City','restaurant','["seafood"]',2,2,'2026-03-11T20:30','2026-03-01T10:00','confirmed',NULL,1,0,'bar',9800,'2026-07-25T18:00'),
 ('seed20','gmail','seed-20','resy','Rosetta',NULL,'Mexico City','restaurant','["italian"]',3,2,'2026-03-12T21:00','2026-03-01T10:05','confirmed',NULL,1,0,'table',12400,'2026-07-25T18:00'),
 ('seed21','gmail','seed-21','eventbrite','Teotihuacan Sunrise Tour',NULL,'Mexico City','activity',NULL,2,2,'2026-03-13T09:00','2026-02-25T14:00','cancelled','2026-03-12T23:20',1,0,NULL,NULL,'2026-07-25T18:00'),
 ('seed22','calendar','seed-22',NULL,'Museo Jumex',NULL,'Mexico City','activity',NULL,1,2,'2026-03-12T16:00',NULL,'attended_unbooked',NULL,1,0,NULL,NULL,'2026-07-25T18:00'),
 -- solo bar seats
 ('seed23','gmail','seed-23','resy','Trick Dog',NULL,'San Francisco','bar','["cocktails"]',2,1,'2026-02-18T21:45','2026-02-18T17:30','confirmed',NULL,0,0,'bar',6400,'2026-07-25T18:00'),
 ('seed24','gmail','seed-24','resy','Trick Dog',NULL,'San Francisco','bar','["cocktails"]',2,1,'2026-05-13T22:00','2026-05-13T18:40','confirmed',NULL,0,0,'bar',5900,'2026-07-25T18:00'),
 ('seed25','gmail','seed-25','eventbrite','SFJAZZ — Late Set',NULL,'San Francisco','event',NULL,2,2,'2026-04-08T21:30','2026-03-20T11:00','confirmed',NULL,0,0,NULL,9000,'2026-07-25T18:00'),
 ('seed26','calendar','seed-26',NULL,'Hotel San Fernando',NULL,'Mexico City','lodging',NULL,3,2,'2026-03-11T15:00','2026-02-18T09:00','confirmed',NULL,1,0,NULL,NULL,'2026-07-25T18:00'),
 -- Notion saves never visited: the aspiration gap (PRD 5.2)
 ('seed27','notion','seed-27',NULL,'Saison',NULL,'San Francisco','restaurant','["californian"]',4,NULL,NULL,NULL,'confirmed',NULL,0,1,NULL,NULL,'2026-07-25T18:00'),
 ('seed28','notion','seed-28',NULL,'Lazy Bear',NULL,'San Francisco','restaurant','["american"]',4,NULL,NULL,NULL,'confirmed',NULL,0,1,NULL,NULL,'2026-07-25T18:00'),
 ('seed29','notion','seed-29',NULL,'Sushi Shin',NULL,'San Francisco','restaurant','["sushi"]',4,NULL,NULL,NULL,'confirmed',NULL,0,1,NULL,NULL,'2026-07-25T18:00'),
 ('seed30','drive_exif','seed-30',NULL,'Tartine Manufactory',NULL,'San Francisco','restaurant','["bakery"]',1,2,'2026-06-06T11:30',NULL,'attended_unbooked',NULL,0,0,NULL,NULL,'2026-07-25T18:00');
