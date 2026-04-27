-- Sample BigQuery Queries for Location Intelligence Workshop
-- These demonstrate how to query OpenStreetMap data for Bangalore

-- Query 1: Find all cafes in Bangalore
SELECT 
    feature_name AS name,
    ST_Y(geometry) AS lat,
    ST_X(geometry) AS lng,
    feature_value AS type
FROM `bigquery-public-data.geo_openstreetmap.planet_features`
WHERE feature_type = 'amenity'
AND feature_value IN ('cafe', 'coffee_shop')
AND ST_WITHIN(
    geometry,
    ST_GEOGFROMTEXT(
        'POLYGON((77.45 12.85, 77.75 12.85, 77.75 13.05, 77.45 13.05, 77.45 12.85))'
    )
)
LIMIT 50;

-- Query 2: Find gyms and fitness centers
SELECT 
    feature_name AS name,
    ST_Y(geometry) AS lat,
    ST_X(geometry) AS lng,
    feature_type,
    feature_value
FROM `bigquery-public-data.geo_openstreetmap.planet_features`
WHERE (feature_type = 'leisure' AND feature_value IN ('fitness_centre', 'gym', 'sports_centre'))
OR (feature_type = 'amenity' AND feature_value = 'gym')
AND ST_WITHIN(
    geometry,
    ST_GEOGFROMTEXT(
        'POLYGON((77.45 12.85, 77.75 12.85, 77.75 13.05, 77.45 13.05, 77.45 12.85))'
    )
)
LIMIT 50;

-- Query 3: Count businesses by category in different areas
SELECT 
    feature_value AS category,
    COUNT(*) as count,
    AVG(ST_Y(geometry)) as avg_lat,
    AVG(ST_X(geometry)) as avg_lng
FROM `bigquery-public-data.geo_openstreetmap.planet_features`
WHERE feature_type IN ('amenity', 'shop', 'leisure')
AND feature_value IN ('cafe', 'restaurant', 'gym', 'bank', 'pharmacy')
AND ST_WITHIN(
    geometry,
    ST_GEOGFROMTEXT(
        'POLYGON((77.45 12.85, 77.75 12.85, 77.75 13.05, 77.45 13.05, 77.45 12.85))'
    )
)
GROUP BY feature_value
ORDER BY count DESC;

-- Query 4: Find businesses near a specific point (e.g., MG Road)
DECLARE center_lat FLOAT64 DEFAULT 12.9738;
DECLARE center_lng FLOAT64 DEFAULT 77.6101;
DECLARE radius_km FLOAT64 DEFAULT 2.0;

SELECT 
    feature_name AS name,
    feature_type,
    feature_value AS category,
    ST_Y(geometry) AS lat,
    ST_X(geometry) AS lng,
    ST_DISTANCE(geometry, ST_GEOGPOINT(center_lng, center_lat)) / 1000 AS distance_km
FROM `bigquery-public-data.geo_openstreetmap.planet_features`
WHERE feature_name IS NOT NULL
AND ST_DWITHIN(
    geometry,
    ST_GEOGPOINT(center_lng, center_lat),
    radius_km * 1000
)
ORDER BY distance_km
LIMIT 20;

-- Query 5: Density analysis - which areas have most restaurants?
SELECT 
    ROUND(ST_Y(geometry), 2) AS lat_grid,
    ROUND(ST_X(geometry), 2) AS lng_grid,
    COUNT(*) AS restaurant_count
FROM `bigquery-public-data.geo_openstreetmap.planet_features`
WHERE feature_type = 'amenity'
AND feature_value = 'restaurant'
AND ST_WITHIN(
    geometry,
    ST_GEOGFROMTEXT(
        'POLYGON((77.45 12.85, 77.75 12.85, 77.75 13.05, 77.45 13.05, 77.45 12.85))'
    )
)
GROUP BY lat_grid, lng_grid
HAVING COUNT(*) > 5
ORDER BY restaurant_count DESC
LIMIT 10;
