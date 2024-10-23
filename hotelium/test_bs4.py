from bs4 import BeautifulSoup

html = '''
<div class="b1c925a97c" data-testid="PropertyHeaderAddressDesktop-wrapper">
    <div class="fe4ce54ee2">
        <a data-atlas-latlng="10.771274626414053,106.69297717780151" data-atlas-bbox="10.75330778596957,106.67468973896139,10.789240395096773,106.71126679860902" data-source="top_link" title="Mandarin Boutique Hotel, Ho Chi Minh City - Check location" id="map_trigger_header_pin" href="#map_opened-map_trigger_header_pin" class="a83ed08757 f88a5204c2 f3e77dfbe7 b98133fb50">
            <span><span class="fcd9eec8fb c2cc050fb8" aria-hidden="true"></span></span>
        </a>
        <span class="f419a93f12">
            <div tabindex="0" class="a53cbfa6de f17adf7576">
                52 Đường Bùi Thị Xuân, District 1, Ho Chi Minh City, Vietnam
                <div aria-hidden="true" class="ac52cd96ed">
                    <div class="a53cbfa6de ac08b954fc">
                        <b>Excellent</b> location — rated 9.5/10!<small>(score from <b>391</b> reviews)</small>
                    </div>
                    <div class="a53cbfa6de">Real guests • Real stays • Real opinions</div>
                </div>
            </div>
        </span>
        <span class="eadba1ffd8">–</span>
        <a data-atlas-latlng="10.771274626414053,106.69297717780151" data-atlas-bbox="10.75330778596957,106.67468973896139,10.789240395096773,106.71126679860902" data-source="top_link" title="Mandarin Boutique Hotel, Ho Chi Minh City - Check location" id="map_trigger_header" href="#map_opened-map_trigger_header" class="a83ed08757 f88a5204c2 a40b576ae6 b98133fb50">
            <span>Excellent location - show map</span>
        </a>
    </div>
</div>
'''

soup = BeautifulSoup(html, 'html.parser')
address = soup.find('div', class_='a53cbfa6de f17adf7576').text.strip()

# \n to a list
address_list = address.split('\n')
print(address_list[0])