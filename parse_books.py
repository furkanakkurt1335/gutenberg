from bs4 import BeautifulSoup
from ebooklib import epub
from get_metadata import prepare_rdf_metadata
from pathlib import Path
import argparse, ebooklib, json, re, requests

def get_args():
    parser = argparse.ArgumentParser(description='Parse books')
    parser.add_argument('-b', '--book_list', type=Path, help='List of books')
    return parser.parse_args()

def download_epub(epub_noimages_link, epub_path):
    response = requests.get(epub_noimages_link)
    with epub_path.open('wb') as file:
        file.write(response.content)

def main():
    args = get_args()
    script_dir = Path(__file__).parent
    rdf_metadata_path = script_dir / 'rdf_metadata.json'
    if not rdf_metadata_path.exists():
        rdf_metadata = prepare_rdf_metadata(rdf_metadata_path)
    else:
        with rdf_metadata_path.open() as file:
            rdf_metadata = json.load(file)

    if args.book_list:
        book_list_path = args.book_list
        with book_list_path.open() as file:
            book_list = json.load(file)
            book_ids = [book['id'] for book in book_list]
    else:
        book_ids = rdf_metadata.keys()

    epubs_dir = script_dir / 'epubs'
    epubs_dir.mkdir(exist_ok=True)
    for book_id in book_ids[:5]:
        epub_path = epubs_dir / f'{book_id}.epub'
        if epub_path.exists():
            continue
        metadata = rdf_metadata[book_id]
        if 'epub_noimages_link' not in metadata:
            print(f'No epub_noimages_link for {book_id}')
            continue
        epub_noimages_link = metadata['epub_noimages_link']
        download_epub(epub_noimages_link, epub_path)
    
    epub_list = sorted(list(epubs_dir.iterdir()), key=lambda x: int(x.stem))
    for epub_path in epub_list:
        book = epub.read_epub(str(epub_path))
        start, end = False, False
        chapters = []
        for item in book.get_items():
            content, media_type = item.get_content(), item.get_type()
            if media_type != ebooklib.ITEM_DOCUMENT:
                continue
            soup = BeautifulSoup(content, 'html.parser')
            if not start:
                start = soup.find('div', id='pg-start-separator')
                if start:
                    start = True
                    continue
            if start and not end:
                end = soup.find('div', id='pg-end-separator')
                if end:
                    break
            if start:
                chapter = soup.find('div', class_='chapter')
                h2 = chapter.find('h2')
                title = h2.text.strip()
                h2.decompose()
                chapter_text = chapter.text.strip()
                chapters.append({'title': title, 'text': chapter_text})
        print(f'Found {len(chapters)} chapters in {epub_path}')

        ebook_id = epub_path.stem
        content_path = script_dir / 'contents'
        content_path.mkdir(exist_ok=True)
        content_path = content_path / f'{ebook_id}.json'
        with content_path.open('w') as file:
            json.dump(chapters, file, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    main()