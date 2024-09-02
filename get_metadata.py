import argparse, csv, json, re, requests, tarfile, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import time

def get_args():
    parser = argparse.ArgumentParser(description='Download metadata and epubs from Project Gutenberg')
    parser.add_argument('-l', '--language', default='en', help='Language of the books to download')
    return parser.parse_args()

def download_catalog(catalog_path):
    url = 'https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv'
    response = requests.get(url)
    with catalog_path.open('wb') as file:
        file.write(response.content)

def prepare_catalog_metadata(script_dir, catalog_metadata_path, language):
    catalog_path = script_dir / 'pg_catalog.csv'
    if not catalog_path.exists():
        download_catalog(catalog_path)

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
            if row['Language'] != language:
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
    print(f'Found {len(metadata)} books in {language}')

    with catalog_metadata_path.open('w') as file:
        json.dump(metadata, file, indent=4, ensure_ascii=False)

    return metadata

def download_rdf_files(rdf_files_path):
    url = 'https://www.gutenberg.org/cache/epub/feeds/rdf-files.tar.zip'

    if rdf_files_path.exists():
        print('rdf-files.tar.zip already exists.')
    else:
        print('Downloading rdf-files.tar.zip...')
        response = requests.get(url)
        with rdf_files_path.open('wb') as file:
            file.write(response.content)
        print('Downloaded rdf-files.tar.zip.')

    tar_file_path = rdf_files_path.parent / 'rdf-files.tar'
    if tar_file_path.exists():
        print('rdf-files.tar already exists.')
    else:
        print('Unzipping rdf-files.tar.zip...')
        with zipfile.ZipFile(rdf_files_path, 'r') as zip_ref:
            zip_ref.extractall(rdf_files_path.parent)
        print('Unzipped rdf-files.tar.zip.')

    rdf_files_dir = rdf_files_path.parent / 'rdf-files'
    if rdf_files_dir.exists():
        print('rdf-files directory already exists.')
    else:
        print('Untarring rdf-files.tar...')
        with tarfile.open(tar_file_path) as file:
            file.extractall(rdf_files_dir)
        print('Untarred rdf-files.tar.')

def prepare_rdf_metadata(script_dir, catalog_metadata, rdf_metadata_path):
    book_ids = sorted(list(catalog_metadata.keys()), key=lambda x: int(x))
    print(f'Found {len(book_ids)} books')

    rdf_files_dir = script_dir / 'rdf-files'
    if not rdf_files_dir.exists():
        rdf_files_path = script_dir / 'rdf-files.tar.zip'
        download_rdf_files(rdf_files_path)

    epub_dir = rdf_files_dir / 'cache/epub'

    namespaces = {
        'dcterms': 'http://purl.org/dc/terms/',
        'pgterms': 'http://www.gutenberg.org/2009/pgterms/',
        'dcam': 'http://purl.org/dc/dcam/',
        'cc': 'http://web.resource.org/cc/',
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'marcrel': 'http://id.loc.gov/vocabulary/relators/',
        'rdfs': 'http://www.w3.org/2000/01/rdf-schema#'
    }

    ebook_id_pattern = re.compile(r'^ebooks/(\d+)$')
    agent_id_pattern = re.compile(r'^2009/agents/(\d+)$')

    rdf_metadata = {}
    agents = {}
    for book_id in book_ids:
        rdf_file = epub_dir / book_id / f'pg{book_id}.rdf'
        if not rdf_file.exists():
            print(f'Could not find {rdf_file} in rdf-files but found in catalog metadata')
            continue

        tree = ET.parse(rdf_file)
        root = tree.getroot()

        ebook = root.find('pgterms:ebook', namespaces)
        rdf_about = ebook.attrib[f"{{{namespaces['rdf']}}}about"]
        ebook_id = ebook_id_pattern.search(rdf_about).group(1)
        publisher = ebook.find('dcterms:publisher', namespaces).text
        license = ebook.find('dcterms:license', namespaces).attrib[f"{{{namespaces['rdf']}}}resource"]
        issued_date = ebook.find('dcterms:issued', namespaces).text
        rights = ebook.find('dcterms:rights', namespaces).text
        downloads = ebook.find('pgterms:downloads', namespaces).text
        editors = []
        for editor in ebook.findall('marcrel:edt', namespaces):
            agent = editor.find('pgterms:agent', namespaces)
            if agent is not None:
                editor = agent.find('pgterms:name', namespaces).text
                id_t = agent.attrib[f"{{{namespaces['rdf']}}}about"]
                agent_id = agent_id_pattern.search(id_t).group(1)
                aliases = [alias.text for alias in agent.findall('pgterms:alias', namespaces)]
                editors.append({'name': editor, 'id': agent_id, 'aliases': aliases})
                agents[agent_id] = {'name': editor, 'aliases': aliases}
            else:
                resource = editor.attrib[f"{{{namespaces['rdf']}}}resource"]
                agent_id = agent_id_pattern.search(resource).group(1)
                if agent_id in agents:
                    editor = agents[agent_id]
                    editors.append({'name': editor['name'], 'id': agent_id, 'aliases': editor['aliases']})
                else:
                    print(f'Could not find agent for editor in {ebook_id}')
        authors = []
        for creator in ebook.findall('dcterms:creator', namespaces):
            agent = creator.find('pgterms:agent', namespaces)
            if agent is not None:
                author = agent.find('pgterms:name', namespaces).text
                id_t = agent.attrib[f"{{{namespaces['rdf']}}}about"]
                agent_id = agent_id_pattern.search(id_t).group(1)
                aliases = [alias.text for alias in agent.findall('pgterms:alias', namespaces)]
                authors.append({'name': author, 'id': agent_id, 'aliases': aliases})
                agents[agent_id] = {'name': author, 'aliases': aliases}
            else:
                resource = creator.attrib[f"{{{namespaces['rdf']}}}resource"]
                agent_id = agent_id_pattern.search(resource).group(1)
                if agent_id in agents:
                    author = agents[agent_id]
                    authors.append({'name': author['name'], 'id': agent_id, 'aliases': author['aliases']})
                else:
                    print(f'Could not find agent for creator in {ebook_id}')
        title = ebook.find('dcterms:title', namespaces)
        if title is not None:
            title = title.text
        else:
            print(f'Could not find title in {ebook_id}')
        language = ebook.find('dcterms:language', namespaces).find('rdf:Description', namespaces).find('rdf:value', namespaces).text
        subjects = []
        for subject in ebook.findall('dcterms:subject', namespaces):
            subject = subject.find('rdf:Description', namespaces).find('rdf:value', namespaces).text
            subjects.append(subject)
        bookshelf = ebook.find('pgterms:bookshelf', namespaces)
        if bookshelf is not None:
            bookshelf = bookshelf.find('rdf:Description', namespaces).find('rdf:value', namespaces).text
        epub_noimages_link, txt_link = None, None
        for has_format in ebook.findall('dcterms:hasFormat', namespaces):
            file = has_format.find('pgterms:file', namespaces)
            link = file.attrib[f"{{{namespaces['rdf']}}}about"]
            if link.endswith('.epub.noimages'):
                epub_noimages_link = link
            elif link.endswith('.txt.utf-8'):
                txt_link = link
            if epub_noimages_link and txt_link:
                break

        rdf_metadata[ebook_id] = {
            'publisher': publisher,
            'license': license,
            'issued_date': issued_date,
            'rights': rights,
            'downloads': downloads,
            'authors': authors,
            'editors': editors,
            'title': title,
            'language': language,
            'subjects': subjects,
            'bookshelf': bookshelf,
            'epub_noimages_link': epub_noimages_link,
            'txt_link': txt_link
        }
    
    with rdf_metadata_path.open('w') as file:
        json.dump(rdf_metadata, file, indent=4, ensure_ascii=False)

def main():
    args = get_args()
    script_dir = Path(__file__).parent

    catalog_metadata_path = script_dir / 'catalog_metadata.json'
    if not catalog_metadata_path.exists():
        prepare_catalog_metadata(script_dir, catalog_metadata_path, args.language)

    with catalog_metadata_path.open() as file:
        catalog_metadata = json.load(file)

    rdf_metadata_path = script_dir / 'rdf_metadata.json'
    if not rdf_metadata_path.exists():
        prepare_rdf_metadata(script_dir, catalog_metadata, rdf_metadata_path)

if __name__ == '__main__':
    main()