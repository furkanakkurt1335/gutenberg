import argparse, json
from pathlib import Path

def get_args():
    parser = argparse.ArgumentParser(description='List subjects with a filter')
    parser.add_argument('-f', '--filter', help='Filter subjects')
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
    subject_set = set()
    for metadata in rdf_metadata.values():
        subjects = metadata['subjects']
        for subject in subjects:
            subject_lower = subject.lower()
            if filter is None or filter in subject_lower:
                subject_set.add(subject)
    print(f'Found {len(subject_set)} subjects')

    subject_list = sorted(list(subject_set))
    subject_list_path = script_dir / 'subject_list.json'
    with subject_list_path.open('w') as file:
        json.dump(subject_list, file, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    main()