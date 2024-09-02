import argparse, json
from pathlib import Path

def get_args():
    parser = argparse.ArgumentParser(description='List books with a filter')
    parser.add_argument('-f', '--filter', help='Filter books')
    return parser.parse_args()

def main():
    args = get_args()
    script_dir = Path(__file__).parent
    rdf_metadata_path = script_dir / 'rdf_metadata.json'
    with rdf_metadata_path.open() as file:
        rdf_metadata = json.load(file)

    filter = None
    if args.filter:
        filter = args.filter.lower()
    book_list = []
    for ebook_id, metadata in rdf_metadata.items():
        subjects = metadata['subjects']
        for subject in subjects:
            if filter is None or filter in subject.lower():
                d_t = metadata
                d_t['id'] = ebook_id
                book_list.append(d_t)
    print(f'Found {len(book_list)} books')

    book_list_path = script_dir / 'book_list.json'
    with book_list_path.open('w') as file:
        json.dump(book_list, file, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    main()