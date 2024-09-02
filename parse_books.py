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
    print(f'Downloaded {epub_path}')

def main():
    args = get_args()
    script_dir = Path(__file__).parent
    rdf_metadata_path = script_dir / 'rdf_metadata.json'
    if not rdf_metadata_path.exists():
        rdf_metadata = prepare_rdf_metadata(rdf_metadata_path)
    else:
        with rdf_metadata_path.open() as file:
            rdf_metadata = json.load(file)
    print('Loaded rdf_metadata.json')

    if args.book_list:
        book_list_path = args.book_list
        with book_list_path.open() as file:
            book_list = json.load(file)
            book_ids = [book['id'] for book in book_list]
    else:
        book_ids = rdf_metadata.keys()

    epubs_dir = script_dir / 'epubs'
    epubs_dir.mkdir(exist_ok=True)
    for book_id in book_ids:
        epub_path = epubs_dir / f'{book_id}.epub'
        if epub_path.exists():
            continue
        metadata = rdf_metadata[book_id]
        if 'epub_noimages_link' not in metadata:
            print(f'No epub_noimages_link for {book_id}')
            continue
        epub_noimages_link = metadata['epub_noimages_link']
        download_epub(epub_noimages_link, epub_path)

    hs = ['h2', 'h3', 'h4', 'h5', 'h6']
    epub_list = sorted(list(epubs_dir.iterdir()), key=lambda x: int(x.stem))
    for epub_path in epub_list:
        book = epub.read_epub(str(epub_path))
        started, ended = False, False
        chapters = []
        for item in book.get_items():
            content, media_type = item.get_content(), item.get_type()
            if media_type != ebooklib.ITEM_DOCUMENT:
                continue
            soup = BeautifulSoup(content, 'html.parser')
            if not started:
                start = soup.find('div', id='pg-start-separator')
                if start:
                    started = True
                    previous_sibling = start.find_previous_sibling()
                    while previous_sibling:
                        previous_sibling.decompose()
                        previous_sibling = start.find_previous_sibling()
            if started and not ended:
                end = soup.find('div', id='pg-end-separator')
                if end:
                    break
            if started:
                chapter_l = soup.find_all('div', class_='chapter')
                if chapter_l:
                    for chapter in chapter_l:
                        for h in hs:
                            headers = chapter.find_all(h)
                            if headers:
                                for header in headers:
                                    title = header.text.strip()
                                    chapter_text, next_sibling = '', header.find_next_sibling()
                                    while next_sibling and next_sibling.name != h:
                                        chapter_text += next_sibling.text.strip()
                                        next_sibling = next_sibling.find_next_sibling()
                                    if not chapter_text:
                                        continue
                                    chapters.append({'title': title, 'text': chapter_text})
                                break
                else:
                    for h in hs:
                        headers = soup.find_all(h)
                        if headers:
                            for header in headers:
                                title = header.text.strip()
                                chapter_text, next_sibling = '', header.find_next_sibling()
                                while next_sibling and next_sibling.name != h:
                                    chapter_text += next_sibling.text.strip()
                                    next_sibling = next_sibling.find_next_sibling()
                                if not chapter_text:
                                    continue
                                chapters.append({'title': title, 'text': chapter_text})
                            break
        print(f'Found {len(chapters)} chapters in {epub_path}')

        ebook_id = epub_path.stem
        content_path = script_dir / 'contents'
        content_path.mkdir(exist_ok=True)
        content_path = content_path / f'{ebook_id}.json'
        with content_path.open('w') as file:
            json.dump(chapters, file, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    main()