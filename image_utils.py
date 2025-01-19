import requests
from PIL import Image
from io import BytesIO

def get_image_src(driver, image_element):
    try:
        return image_element.get_attribute("src")
    except Exception:
        return driver.execute_script("return arguments[0].getAttribute('src');", image_element)

def is_valid_image(image_url):
    try:
        if image_url.startswith("data:") or not image_url.startswith("http"):
            return False
        response = requests.get(image_url, stream=True)
        if response.status_code == 200:
            image = Image.open(BytesIO(response.content))
            width, height = image.size
            return width >= 256 and height >= 256
    except Exception as e:
        print(f"Error validating image {image_url}: {e}")
    return False
