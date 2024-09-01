import argparse, csv, json, requests
from pathlib import Path

def get_args():
    parser = argparse.ArgumentParser(description='Download metadata and epubs from Project Gutenberg')
    parser.add_argument('-l', '--language', default='en', help='Language of the books to download')
    return parser.parse_args()

def download_catalog():
    url = 'https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv'
    response = requests.get(url)
    with open('pg_catalog.csv', 'wb') as file:
        file.write(response.content)

def main():
    args = get_args()
    script_dir = Path(__file__).parent
    catalog_path = script_dir / 'pg_catalog.csv'
    if not catalog_path.exists():
        download_catalog()
    
    keys_to_include = ['Issued', 'Title', 'Language', 'Authors', 'Subjects']
    matching_keys = {
        'Issued': 'issued_date',
        'Title': 'title',
        'Language': 'language',
        'Authors': 'authors',
        'Subjects': 'subjects'
    }
    with catalog_path.open() as file:
        reader = csv.DictReader(file)
        metadata = {}
        for row in reader:
            type_t = row['Type']
            if type_t != 'Text':
                continue
            if row['Language'] != args.language:
                continue
            id_t = row['Text#']
            metadata[id_t] = {}
            for key in keys_to_include:
                matched_key = matching_keys[key]
                if key in ['Authors', 'Subjects']:
                    value = row[key]
                    metadata[id_t][matched_key] = [item.strip() for item in value.split(';')]
                else:
                    metadata[id_t][matched_key] = row[key]
    print(f'Found {len(metadata)} books in {args.language}')
    
    metadata_path = script_dir / 'metadata.json'
    with metadata_path.open('w') as file:
        json.dump(metadata, file, indent=2)

if __name__ == '__main__':
    main()