-- 200_gi_geo_shape.sql
-- PostGIS geometry columns on gi_details, derived from unioning GISCO admin-unit
-- boundaries (gisco_units) that a GI's geographical_area resolves to.
--   geo_shape    : the actual footprint (MultiPolygon, WGS84) for spatial queries
--   geo_centroid : label/pin point
--   geo_area_km2 : display + sanity check
-- geo_geometry (JSONB, pre-existing) keeps the simplified GeoJSON Feature the map reads.
ALTER TABLE gi_details ADD COLUMN IF NOT EXISTS geo_shape    geometry(MultiPolygon, 4326);
ALTER TABLE gi_details ADD COLUMN IF NOT EXISTS geo_centroid geometry(Point, 4326);
ALTER TABLE gi_details ADD COLUMN IF NOT EXISTS geo_area_km2 double precision;
ALTER TABLE gi_details ADD COLUMN IF NOT EXISTS geo_geom_confidence varchar(24);  -- exact_nuts | name_nuts | name_lau | union | unresolved
CREATE INDEX IF NOT EXISTS idx_gi_geo_shape ON gi_details USING gist (geo_shape);
