from bs4 import BeautifulSoup
from ebooklib import epub
from get_metadata import prepare_rdf_metadata
from pathlib import Path
import argparse, ebooklib, json, re, requests

def get_args():
    parser = argparse.ArgumentParser(description='Parse books')
    parser.add_argument('-b', '--book_list', type=Path, help='List of books')
    parser.add_argument('-f', '--format', type=str, default='epub', help='Format of books')
    return parser.parse_args()

def download(link, path):
    response = requests.get(link)
    with path.open('wb') as file:
        file.write(response.content)
    print(f'Downloaded {path}')

def parse_book(book_format, book_path):
    if book_format == 'epub':
        hs = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
        book = epub.read_epub(str(book_path))
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
                    ended = True
                    next_sibling = end.find_next_sibling()
                    while next_sibling:
                        next_sibling.decompose()
                        next_sibling = end.find_next_sibling()
            if started:
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
                if ended:
                    break
        print(f'Found {len(chapters)} chapters in {book_path}')
        return chapters
    elif book_format == 'txt':
        start_pattern = re.compile(r'\*\*\* START OF THE PROJECT GUTENBERG EBOOK .* \*\*\*')
        end_pattern = re.compile(r'\*\*\* END OF THE PROJECT GUTENBERG EBOOK .* \*\*\*')
        with book_path.open() as file:
            content = file.read()
        start = start_pattern.search(content)
        if start:
            start = start.end()
            content = content[start:]
        end = end_pattern.search(content)
        if end:
            end = end.start()
            content = content[:end]
        return content

def main():
    args = get_args()
    book_format = args.format
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

    book_dir = script_dir / f'{book_format}s'
    book_dir.mkdir(exist_ok=True)
    books_downloaded = []
    for book_id in book_ids:
        book_path = book_dir / f'{book_id}.{book_format}'
        if book_path.exists():
            continue
        metadata = rdf_metadata[book_id]
        title, authors = metadata['title'], metadata['authors']
        for author in authors:
            author_id = author['id']
            if (author_id, title) in books_downloaded:
                print(f'Already downloaded {author_id} - {title}')
                continue
            aliases = author['aliases']
            for alias in aliases:
                if (alias, title) in books_downloaded:
                    continue
        if book_format == 'epub':
            metadata_key = 'epub_noimages_link'
        elif book_format == 'txt':
            metadata_key = 'txt_link'
        if metadata_key not in metadata:
            print(f'No {metadata_key} for {book_id}')
            continue
        link = metadata[metadata_key]
        download(link, book_path)
        for author in authors:
            author_id = author['id']
            books_downloaded.append((author_id, title))
            aliases = author['aliases']
            for alias in aliases:
                books_downloaded.append((alias, title))

    book_list = sorted(list(book_dir.iterdir()), key=lambda x: int(x.stem))
    for book_path in book_list:
        content = parse_book(book_format, book_path)
        book_id = book_path.stem
        content_path = script_dir / 'contents'
        content_path.mkdir(exist_ok=True)
        if book_format == 'txt':
            content_path = content_path / f'{book_id}.txt'
            with content_path.open('w') as file:
                file.write(content)
        else:
            content_path = content_path / f'{book_id}.json'
            with content_path.open('w') as file:
                json.dump(content, file, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    main()