import hashlib
import json
import logging
import mimetypes
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests import HTTPError

from labfolder_migration import LabfolderClient

ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = ROOT / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / 'labfolder_fetcher.log'

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler(str(LOG_FILE)), ], )
logger = logging.getLogger(__name__)


class LabFolderFetcher:
    '''
    Wraps the Labfolder client to fetch entries, handle token refresh,
    and save elements including TABLE, WELL_PLATE, TEXT, FILE, IMAGE, DATA.
    '''

    def __init__ (self, email: str, password: str, base_url: str) -> None:
        self.email = email
        self.password = password
        self.base_url = base_url.rstrip('/')
        self._client = LabfolderClient(email, password, self.base_url)
        self._client.login()

    def _get (self, endpoint: str,
              params: Optional[Dict[str, Any]] = None) -> requests.Response:
        try:
            return self._client.get(endpoint, params=params)
        except HTTPError as e:
            if e.response.status_code == 401:
                logger.info('Token expired, re-logging in')
                self._client.login()
                return self._client.get(endpoint, params=params)
            raise

    def fetch_entries (self, expand: Optional[List[str]] = None,
                       limit: int = 50, include_hidden: bool = True) -> List[
        Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        offset = 0
        expand_str = ','.join(expand) if expand else None

        while True:
            params: Dict[str, Any] = {
                'limit'         : limit,
                'offset'        : offset,
                'include_hidden': include_hidden,
                }
            if expand_str:
                params['expand'] = expand_str
            resp = self._get('entries', params=params)
            batch = resp.json()
            if not isinstance(batch, list):
                raise RuntimeError(f'Unexpected entries format: {batch!r}')
            entries.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return entries

    def fetch_text (self, element: Dict[str, Any]) -> str:
        text_id = f"elements/text/{element['id']}"
        resp = self._get(text_id)
        return resp.json().get('content', '')

    def fetch_file (self, element: Dict[str, Any]) -> Optional[Path]:
        file_id = element.get('id')
        if not file_id:
            logger.error('Invalid file element (no id) %r', element)
            return None

        try:
            resp = self._get(f"elements/file/{file_id}/download")
        except HTTPError as e:
            logger.error('Failed to download file %s: %s', file_id, e)
            return None

        content_disp = resp.headers.get('Content-Disposition', '')
        filename = 'unnamed_file'
        if 'filename=' in content_disp:
            parts = content_disp.split('filename=')
            if len(parts) > 1:
                filename = parts[-1].strip().strip('"')

        tmp_dir = Path(tempfile.gettempdir())
        temp_path = tmp_dir / filename
        try:
            with temp_path.open('wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        except (OSError, requests.exceptions.RequestException) as e:
            logger.error('Error writing file %s: %s', temp_path, e)
            return None

        return temp_path

    def fetch_image (self, element: Dict[str, Any]) -> Optional[Path]:
        image_id = element.get('id')
        if not image_id:
            logger.error('Invalid image element (no id) %r', element)
            return None

        try:
            resp = self._get(f"elements/image/{image_id}/original-data")
        except HTTPError as e:
            logger.error('Failed to download image %s: %s', image_id, e)
            return None

        content_disp = resp.headers.get('Content-Disposition', '')
        filename = 'unnamed_image'
        if 'filename=' in content_disp:
            parts = content_disp.split('filename=')
            if len(parts) > 1:
                filename = parts[-1].strip().strip('"')

        tmp_dir = Path(tempfile.gettempdir())
        temp_path = tmp_dir / filename
        try:
            with temp_path.open('wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        except (OSError, requests.exceptions.RequestException) as e:
            logger.error('Error writing image file %s: %s', temp_path, e)
            return None

        return temp_path

    def fetch_data (self, element: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data_id = element.get('id')
        if not data_id:
            logger.error('Invalid data element (no id): %r', element)
            return None
        try:
            resp = self._get(f"elements/data/{data_id}")
            return resp.json()
        except HTTPError as e:
            logger.error('Failed to fetch data element %s: %s', data_id, e)
            return None
        except ValueError as e:
            logger.error('Invalid JSON returned for data element %s: %s',
                         data_id, e)
            return None

    def fetch_table (self, element: Dict[str, Any]) -> Optional[
        Dict[str, Any]]:
        table_id = element.get('id')
        if not table_id:
            logger.error('Invalid table element (no id): %r', element)
            return None
        try:
            resp = self._get(f"elements/table/{table_id}")
            return resp.json()
        except HTTPError as e:
            logger.error('Failed to fetch table element %s: %s', table_id, e)
            return None
        except ValueError as e:
            logger.error('Invalid JSON returned for table element %s: %s',
                         table_id, e)
            return None

    def fetch_well_plate (self, element: Dict[str, Any]) -> Optional[
        Dict[str, Any]]:
        plate_id = element.get('id')
        if not plate_id:
            logger.error('Invalid well plate element (no id): %r', element)
            return None
        try:
            resp = self._get(f"elements/well-plate/{plate_id}")
            return resp.json()
        except HTTPError as e:
            logger.error('Failed to fetch well plate element %s: %s', plate_id,
                         e)
            return None
        except ValueError as e:
            logger.error('Invalid JSON returned for well plate element %s: %s',
                         plate_id, e)
            return None

    def __get_node_from_metadata (self, json_metadata: Dict[str, Any],
                                  entry_folder: Path) -> Dict[str, Any]:
        node: Dict[str, Any] = {}
        node['@id'] = f"./{entry_folder.name}/{json_metadata.get('id')}"
        node['@type'] = 'File'
        node['name'] = json_metadata.get('file_name') or json_metadata.get(
            'title') or 'Unknown'
        size = int(json_metadata.get('file_size', 0))
        if size > 0:
            node['contentSize'] = size
        node['encodingFormat'] = json_metadata.get(
            'content_type') or json_metadata.get('original_file_content_type')
        return node

    def __get_csvs_from_json (self, json_metadata: Dict[str, Any]) -> List[
        Tuple[str, str]]:
        sheets = json_metadata.get('sheets', {})
        return [(name, content) for name, content in sheets.items()]

    def __get_unique_enough_id (self) -> str:
        return str(uuid.uuid4())

    def __get_node_from_csv (self, csv_id: str, csv_content: str,
                             entry_folder: Path) -> Dict[str, Any]:
        node: Dict[str, Any] = {}
        node['@id'] = f"./{entry_folder.name}/{csv_id}.csv"
        node['@type'] = 'File'
        node['name'] = f'{csv_id}.csv'
        node['encodingFormat'] = 'text/csv'
        node['contentSize'] = len(csv_content)
        return node

    def _handle_table_element (self, element: Dict[str, Any],
                               entry_folder: Path,
                               crate_metadata: Dict[str, Any],
                               files: List[str]) -> None:
        if element['type'] == 'TABLE':
            json_metadata = self.fetch_table(element)
        else:
            json_metadata = self.fetch_well_plate(element)
        if not json_metadata:
            return
        node = self.__get_node_from_metadata(json_metadata, entry_folder)
        json_path = entry_folder / f"{json_metadata['id']}.json"
        with json_path.open('w') as jf:
            json.dump(json_metadata, jf, indent=2)
        node['sha256'] = hashlib.sha256(
            json.dumps(json_metadata, indent=2).encode()).hexdigest()
        crate_metadata['@graph'].append(node)
        files.append(node['@id'])
        csvs = self.__get_csvs_from_json(json_metadata)
        for sheet_name, csv_content in csvs:
            csv_id = self.__get_unique_enough_id()
            csv_node = self.__get_node_from_csv(csv_id, csv_content,
                                                entry_folder)
            csv_path = entry_folder / f"{csv_id}.csv"
            with csv_path.open('w') as cf:
                cf.write(csv_content)
            csv_node['sha256'] = hashlib.sha256(
                csv_content.encode()).hexdigest()
            crate_metadata['@graph'].append(csv_node)
            files.append(csv_node['@id'])

    def process_entry (self, entry: Dict[str, Any], output_dir: Path) -> None:
        '''
        Process a single entry: creates its folder, fetches each element type,
        saves to disk, builds crate_metadata graph and file list.
        '''
        entry_folder = output_dir / str(entry['id'])
        entry_folder.mkdir(parents=True, exist_ok=True)
        crate_metadata: Dict[str, Any] = {
            '@graph': []
            }
        files: List[str] = []

        for element in entry.get('elements', []):
            typ = element.get('type')
            if typ in ('TABLE', 'WELL_PLATE'):
                self._handle_table_element(element, entry_folder,
                                           crate_metadata, files)
            elif typ == 'TEXT':
                content = self.fetch_text(element)
                text_filename = f"{element['id']}.txt"
                text_path = entry_folder / text_filename
                with text_path.open('w') as tf:
                    tf.write(content)
                sha = hashlib.sha256(content.encode()).hexdigest()
                node = {
                    '@id'           : f"./{entry_folder.name}/{text_filename}",
                    '@type'         : 'Text',
                    'name'          : text_filename,
                    'contentSize'   : len(content),
                    'encodingFormat': 'text/plain',
                    'sha256'        : sha
                    }
                crate_metadata['@graph'].append(node)
                files.append(node['@id'])
            elif typ == 'FILE':
                file_path = self.fetch_file(element)
                if file_path and file_path.exists():
                    dest = entry_folder / file_path.name
                    file_path.replace(dest)
                    size = dest.stat().st_size
                    mimetype, _ = mimetypes.guess_type(dest)
                    encoding = mimetype or 'application/octet-stream'
                    data = dest.read_bytes()
                    sha = hashlib.sha256(data).hexdigest()
                    node = {
                        '@id'           : f"./{entry_folder.name}/{dest.name}",
                        '@type'         : 'File',
                        'name'          : dest.name,
                        'contentSize'   : size,
                        'encodingFormat': encoding,
                        'sha256'        : sha
                        }
                    crate_metadata['@graph'].append(node)
                    files.append(node['@id'])
            elif typ == 'IMAGE':
                img_path = self.fetch_image(element)
                if img_path and img_path.exists():
                    dest = entry_folder / img_path.name
                    img_path.replace(dest)
                    size = dest.stat().st_size
                    mimetype, _ = mimetypes.guess_type(dest)
                    encoding = mimetype or 'image/*'
                    data = dest.read_bytes()
                    sha = hashlib.sha256(data).hexdigest()
                    node = {
                        '@id'           : f"./{entry_folder.name}/{dest.name}",
                        '@type'         : 'Image',
                        'name'          : dest.name,
                        'contentSize'   : size,
                        'encodingFormat': encoding,
                        'sha256'        : sha
                        }
                    crate_metadata['@graph'].append(node)
                    files.append(node['@id'])
            elif typ == 'DATA':
                json_data = self.fetch_data(element)
                if json_data:
                    data_filename = f"{element['id']}.json"
                    data_path = entry_folder / data_filename
                    with data_path.open('w') as df:
                        json.dump(json_data, df, indent=2)
                    sha = hashlib.sha256(
                        json.dumps(json_data).encode()).hexdigest()
                    node = {
                        '@id'           : f"./{entry_folder.name}/{data_filename}",
                        '@type'         : 'File',
                        'name'          : data_filename,
                        'contentSize'   : len(json.dumps(json_data)),
                        'encodingFormat': 'application/json',
                        'sha256'        : sha
                        }
                    crate_metadata['@graph'].append(node)
                    files.append(node['@id'])
            else:
                logger.debug('Skipping unsupported element type %s', typ)

        crate_path = entry_folder / 'crate-metadata.json'
        with crate_path.open('w') as cmf:
            json.dump(crate_metadata, cmf, indent=2)
