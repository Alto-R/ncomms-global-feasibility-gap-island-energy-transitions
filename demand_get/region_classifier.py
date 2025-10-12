import pandas as pd

def classify_region(lat, lon, country=None):
    """
    Classify island region based on latitude/longitude coordinates
    
    Args:
        lat: Latitude
        lon: Longitude  
        country: Country name (optional, used for refinement)
    
    Returns:
        Region: 'APAC', 'Europe', 'US', or 'Unknown'
    """
    
    # Europe: 35-71°N, -25-40°E (including UK, Nordic countries)
    if 35 <= lat <= 71 and -25 <= lon <= 40:
        return 'Europe'
    
    # United States and territories
    if country:
        country_lower = country.lower()
        # 将美国和加拿大都归类为 'US' 区域
        if 'united states' in country_lower or 'canada' in country_lower:
            return 'US'
    
    # US mainland and Alaska: 24-71°N, -180 to -65°W
    if 24 <= lat <= 71 and -180 <= lon <= -65:
        return 'US'
    
    # US Pacific territories (Hawaii, Guam, etc): 13-22°N, -180 to -155°W
    if 13 <= lat <= 22 and -180 <= lon <= -155:
        return 'US'
    
    # APAC region boundaries
    apac_regions = [
        # East Asia: 20-50°N, 100-145°E (China, Japan, Korea)
        (20, 50, 100, 145),
        # Southeast Asia: -10-25°N, 90-145°E (Indonesia, Philippines, etc)
        (-10, 25, 90, 145),
        # South Asia: 5-40°N, 60-100°E (India, Sri Lanka)
        (5, 40, 60, 100),
        # Oceania: -50-0°S, 110-180°E (Australia, New Zealand, Pacific islands)
        (-50, 0, 110, 180),
        # Pacific islands: -30-30°N, 130-180°E
        (-30, 30, 130, 180),
        # Indian Ocean: -40-10°N, 40-100°E (Mauritius, Maldives)
        (-40, 10, 40, 100),
    ]
    
    for lat_min, lat_max, lon_min, lon_max in apac_regions:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return 'APAC'
    
    # Special cases based on country
    if country:
        country_lower = country.lower()
        
        # Additional APAC countries
        apac_countries = [
            'japan', 'china', 'philippines', 'indonesia', 'australia', 
            'new zealand', 'fiji', 'vanuatu', 'mauritius', 'india',
            'sri lanka', 'maldives', 'singapore', 'malaysia', 'thailand',
            'vietnam', 'south korea'
        ]
        
        if any(apac_country in country_lower for apac_country in apac_countries):
            return 'APAC'
        
        # European countries
        european_countries = [
            'united kingdom', 'uk', 'ireland', 'france', 'spain', 'portugal',
            'italy', 'greece', 'norway', 'sweden', 'denmark', 'finland',
            'iceland', 'netherlands', 'belgium', 'germany', 'malta'
        ]
        
        if any(eu_country in country_lower for eu_country in european_countries):
            return 'Europe'
        
        # Greenland (part of Denmark, but geographically separate)
        if 'greenland' in country_lower:
            return 'Europe'
    
    # Default to Unknown if no clear classification
    return 'Unknown'

def update_regions_in_csv(csv_path, output_path=None):
    """
    Update CSV file with Region column based on coordinates
    
    Args:
        csv_path: Path to input CSV file
        output_path: Path for output CSV (if None, overwrites input)
    """
    # Read the CSV
    df = pd.read_csv(csv_path)
    
    # Apply region classification
    df['Region'] = df.apply(lambda row: classify_region(
        row['Lat'], 
        row['Long'], 
        row.get('Country', None)
    ), axis=1)
    
    # Save the updated CSV
    output_file = output_path if output_path else csv_path
    df.to_csv(output_file, index=False)
    
    # Print summary
    region_counts = df['Region'].value_counts()
    print(f"Updated {len(df)} islands:")
    for region, count in region_counts.items():
        print(f"  {region}: {count} islands")
    
    return df

if __name__ == "__main__":
    # Update the test CSV file
    df = update_regions_in_csv('cluster_island.csv')
    df.to_csv('cluster_island_withregion.csv')
    print("\nSample of updated data:")
    print(df[['Country', 'Island', 'Lat', 'Long', 'Region']].head(10))