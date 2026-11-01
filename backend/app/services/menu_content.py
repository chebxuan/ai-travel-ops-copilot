"""English Menu storytelling mapped to actual product days, without source prices."""
import json
from copy import deepcopy

from backend.app.core.paths import ROOT


def load_content():
    from backend.app.storage.repository import database_enabled, dataset
    if database_enabled():
        documents = dataset()['documents']
        return documents['highlights'], documents['presentation']
    base = ROOT / 'data/products'
    return (json.loads((base / 'attraction_highlights.json').read_text()),
            json.loads((base / 'menu_presentation.json').read_text()))


def story(spec, city_content, city):
    if 'route' in spec:
        original = city_content['routes'][spec['route']]
        indices = spec.get('attractions', range(len(original['attractions'])))
        highlights = [deepcopy(original['attractions'][index]) for index in indices]
        title, description = original['title'], original['description']
    elif 'activity' in spec:
        original = city_content['activities'][spec['activity']]
        title, description = spec['activity'], original['description']
        highlights = [{'name': title, 'description': description}]
    else:
        title, description, highlights = spec['title'], spec['description'], []
    # Bundled source labels sometimes cover places outside a particular product.
    for highlight in highlights:
        name = highlight['name']
        if city == '云南' and name == 'Erhai Lake & Xizhou Town':
            highlight.update(name='Erhai Lake', description='The mirror of the Cangshan mountains, a lakeside landscape of Bai culture.')
        if city == '广州' and 'Thirteen-Hongs' in name:
            highlight.update(name='Xiguan Folk Museum & Canton Tower', description='Authentic Cantonese life and Guangzhou’s slender city icon.')
        if city == '广州' and 'Huiji' in name:
            highlight.update(name='Sun Yat-sen Memorial Hall', description='The legacy of the Father of Modern China and the city’s republican history.')
        if name == '72 Strange Towers':
            highlight['description'] = 'A soaring interpretation of Tujia-style stilt architecture.'
        if name == 'Tianmen Mountain Excursion':
            highlight['description'] = 'Mountain cableway, the natural Heaven’s Gate arch and cliffside glass skywalks.'
    title = spec.get('title', title).replace('Speical', 'Special').replace('Yangze', 'Yangtze')
    return {'title': title, 'description': spec.get('description', description),
            'highlights': [{'name': item['name'], 'description': item['description']} for item in highlights],
            'alternatives': [story(branch, city_content, city) for branch in spec.get('alternatives', [])],
            'choice': spec.get('choice')}


def product_menu(product):
    content, presentation = load_content()
    city = product['city']
    spec = presentation['products'][product['product_id']]
    city_content = content[city]
    days = [{'day': index + 1, **story(day, city_content, city)} for index, day in enumerate(spec['days'])]
    intro = city_content['routes']['Route 1']['description'] if city in ['贵州', '云南'] else presentation.get('introductions', {}).get(product['product_id'], '')
    return {'title': presentation['product_titles'][product['product_id']],
            'city_name': presentation['city_names'][city], 'introduction': intro,
            'days': days, 'overview': [story(route, city_content, city) for route in spec.get('overview', [])],
            'notice': 'This journey combines Chongqing, Dazu and a Three Gorges cruise. The day-by-day cruise programme and return connection will be confirmed separately.' if spec.get('overview') else ''}


def experience_content(product, name):
    content, presentation = load_content()
    display = presentation['optional_labels'][name]
    activity = content[product['city']]['activities'].get(display['activity'], {})
    # A shared theatre tradition may be documented under Chongqing instead.
    if not activity and display['activity'] == 'Sichuan Opera Face-Changing':
        activity = content['重庆']['activities'][display['activity']]
    return {'name': display['name'], 'description': activity.get('description') or presentation['optional_descriptions'].get(name, ''),
            'duration': activity.get('duration'), 'price_status': 'pending_confirmation'}
