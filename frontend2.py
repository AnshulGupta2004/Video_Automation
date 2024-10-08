import os
import streamlit as st
import requests
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
import moviepy.editor as mp
from dotenv import load_dotenv
from groq import Groq
import textwrap
import re
from PIL import Image, ImageDraw, ImageFont, ImageChops
import cv2
import numpy as np
import io
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from rembg import remove
import shutil

# Load environment variables from .env file
load_dotenv()

# Function to get car information from the API
def carscope_details(car_number):
    url = "https://crm.nxcar.in/api/driveaway_data"
    payload = {"vehiclenumber": car_number}
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error: Received {response.status_code} status code")
        return None

# Function to get car information from the API
def fetch_images(car_number):
    url = "https://crm.nxcar.in/api/fetchCarVideoImages"
    payload = {
        "vehiclenumber": car_number
    }   
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"Error: {response.status_code}")
        return None
    

def banner_image(car_number):
    output_folder = r"video_images"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    url = "https://crm.nxcar.in/api/fetchBannerImage"
    payload = {
        "vehiclenumber": car_number
    }   
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        image_data = response.content
        if image_data:
            output_image_path = r"video_images\1.png"
            with open(output_image_path, 'wb') as file:
                file.write(image_data)
            print(f"Image saved at {output_image_path}")
    else:
        print(f"Error: {response.status_code}")
        return None

def generate_script(prompt):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    system_prompt = {
        "role": "system",
        "content": "You are a helpful assistant. You generate concise and clear scripts for vehicle promotions."
    }
    chat_history = [system_prompt, {"role": "user", "content": prompt}]
    
    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=chat_history,
        max_tokens=500,
        temperature=1.3
    )

    return response.choices[0].message.content.strip()

def trim_image(image, target_size=(3840, 2160)):
    bbox = ImageChops.difference(image, Image.new(image.mode, image.size, (0, 0, 0, 0))).getbbox()
    if bbox:
        return image.crop(bbox)  # Crop the image based on the bounding box
    return image

# Function to extract the 7th and 8th images and generate frames (using frame2, frame3, and frame4)
def process_vehicle_images(vehicle_folders, car_infos):
    output_folder = r"video_images"
    # Check if output folder exists, if not, create it
    
    
    
    image_counter = 2  # Start the image naming from 1
    if len(vehicle_folders)==0:
        print("Vehicle images list is null")
    for vehicle_folder, car_info in zip(vehicle_folders, car_infos):
        print(f"Processing vehicle folder: {vehicle_folder}")
        
        # List all files in the current vehicle folder
        files = sorted(os.listdir(vehicle_folder), key=natural_sort_key)
        print(f"Found {len(files)} files in folder: {vehicle_folder}")
        
        # Ensure there are at least 8 images per vehicle
        if len(files) >= 8:
            # Get paths for the 7th and 8th images
            seventh_image_path = os.path.join(vehicle_folder, files[6])  # 7th image
            eighth_image_path = os.path.join(vehicle_folder, files[7])   # 8th image

            print(f"7th Image Path: {seventh_image_path}, 8th Image Path: {eighth_image_path}")

            # Remove background from the 8th image and process through frame2 and frame3
            eighth_image_no_bg = remove_background(eighth_image_path)

            if eighth_image_no_bg is not None:
                print(f"Processing 8th image for {vehicle_folder} through frame2")
                frame2_html = frame2(car_info, eighth_image_no_bg)
                output_image_2 = os.path.join(output_folder, f"{image_counter}.png")
                html_to_image(frame2_html, output_image_2)
                image_counter += 1

                print(f"Processing 8th image for {vehicle_folder} through frame3")
                frame3_html = frame3(car_info, eighth_image_no_bg)
                output_image_3 = os.path.join(output_folder, f"{image_counter}.png")
                html_to_image(frame3_html, output_image_3)
                image_counter += 1
            else:
                print(f"Failed to remove background for 8th image: {eighth_image_path}")

            # Remove background from the 7th image and process through frame4
            seventh_image_no_bg = remove_background(seventh_image_path)

            if seventh_image_no_bg is not None:
                print(f"Processing 7th image for {vehicle_folder} through frame4")
                frame4_html = frame4(car_info, seventh_image_no_bg)
                output_image_4 = os.path.join(output_folder, f"{image_counter}.png")
                html_to_image(frame4_html, output_image_4)
                image_counter += 1
            else:
                print(f"Failed to remove background for 7th image: {seventh_image_path}")

            print(f"Processed {vehicle_folder} - 7th and 8th images")

            # Process all images in the folder using frame5 (3D perspective)
            # images_3d = "3d_images" 
            # if not os.path.exists(images_3d):
            #     os.makedirs(images_3d)
            for file in files:
                image_path = os.path.join(vehicle_folder, file)
                if image_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                    image_no_bg = remove_background(image_path)
                    if image_no_bg is not None:
                        print(f"Processing {file} through frame5 for 3D perspective")
                        frame5_html = frame5(image_no_bg)
                        output_image_5 = os.path.join(vehicle_folder, f"{file}")
                        html_to_image(frame5_html, output_image_5)
                    else:
                        print(f"Failed to remove background for image: {image_path}")
        else:
            print(f"Skipping {vehicle_folder} - not enough images (found {len(files)} images).")

    last_image(output_folder, image_counter)


def last_image(output_folder, count):
    output_path = os.path.join(output_folder, f"{count}.png")
    input_path = r"C:\Users\hp\NXcar\Video\image_2\image22.png"
    image = Image.open(input_path)
    
    # Save the image to the output path
    image.save(output_path)
    
    print(f"Image saved to {output_path}")


def natural_sort_key(s):
    return [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', s)]


def html_to_image(html_code, output_path, width=1920, height=1080):
    # Create a temporary HTML file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        f.write(html_code)
        temp_html_path = f.name

    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument(f"--window-size={width},{height}")

    # Set up the Chrome driver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Load the HTML file
        driver.get(f"file://{temp_html_path}")

        # Set the viewport size
        driver.set_window_size(width, height)

        # Capture the screenshot
        screenshot = driver.get_screenshot_as_png()

        # Convert the screenshot to an image
        image = Image.open(io.BytesIO(screenshot))

        # Save the image
        image.save(output_path)
        print(f"Image saved successfully: {output_path}")

    finally:
        # Close the browser and remove the temporary file
        driver.quit()
        os.unlink(temp_html_path)

def frame2(car_info,image):
    html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Document</title>
  <style>
    *{{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}
    .box{{
      width: 100%;  
      height: 100vh;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      text-transform: uppercase;
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background-image: url('C:/Users/hp/NXcar/Video/bg.png');
      background-position: center;
      background-repeat: no-repeat;
      background-size: cover;
    }}
     .container{{
      width: 100%;  
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
    }}
    .heading{{
      width: 100%;
      color: teal;
      text-align: center;
      font-weight: bold;
      font-size: 50px;
      margin-bottom: 100px;
    }}
    .left{{
      width:130%;
      padding: 0px;
      height: 590px;
      /* border: 1px solid red; */
      overflow: hidden;
      margin-top: 170px;
      margin-left: -850px;
    }}
    .left img{{
    width: 150%;
      height: 600px;
    display: block;
    object-fit: contain;
    }}

    .right{{
      width: 48%;
      display: flex;
      justify-content: flex-start;
      align-items: flex-start;
      flex-direction: column;
      margin-top: -1400px;
      margin-left: 1200px;
    }}
    .tabs{{
      width: 80%;
      font-size: 30px;
      font-weight: bold;
      color: white;
      background-color: teal;
      padding: 18px 0;
      margin-bottom: 12px;
      text-align: center;
      border-radius: 8px;
    }}
  </style>
</head>
<body>
  <div class="box">
    <div class="container">
    <div class="heading">{car_info['rc_report_generate']['vehicleManufacturerName']}, {car_info['rc_report_generate']['model']}</div>
    <div class="left">
      <img src={image} alt="Car Image">
    </div>
    <div class="right">
      <div class="tabs">{car_info['rc_report_generate']['normsType']}</div>
      <div class="tabs">model: {car_info["makeYear"].split("/")[1]}</div>
      <div class="tabs">Distance:{car_info["kilometers"]} km</div>
    </div>
  </div>
  </div>
</body>
</html>
    """
    return html_template

def frame3(car_info,image):
    # Check if offerPrice exists
    offer_price_html = ""
    if car_info.get("offerPrice"):
        offer_price_html = f"""
        <div class="line"></div>
        <div class="green">Offer price </div>
        <div class="yellow">Rs. {car_info["offerPrice"]}</div>
        """

    html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Document</title>
  <style>
    *{{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}
    .box{{
      width: 100%;  
      height: 100vh;
      display: flex;
      justify-content: space-around;
      align-items: center;
      flex-wrap: wrap;
      text-transform: uppercase;
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background-image: url('C:/Users/hp/NXcar/Video/bg.png');
      background-position: center;
      background-repeat: no-repeat;
      background-size: cover;
    }}
     .container{{
      width: 100%;  
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
    }}
    .heading{{
      /* margin-top: -2000px; */
      width: 100%;
      color: teal;
      text-align: center;
      font-weight: bold;
      font-size: 50px;
    }}

.left{{
      width:130%;
      padding: 0px;
      height: 600px;
      /* border: 1px solid red; */
      overflow: hidden;
      margin-top: 230px;
      margin-left: -750px;
    }}
    .left img{{
    width: 150%;
      height: 600px;
    display: block;
    object-fit: contain;
    }}

    .right{{
      width: 25%;
      border: 2px solid teal;
  border-radius: 16px;
  padding: 12px 50px;
  text-align: left;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
      margin-top: -350px;
      /* margin-left: 900px; */
    }}


    .flex{{
      /* margin-top: -100px; */
      width: 100%;
      padding: 12px 0;
      display: flex;
      align-items: center;
      justify-content: space-around;
      background-color: teal;
    }}
    .flex2{{
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: space-around;
      
    }}
    .number{{
      font-size: 50px;
      font-size: 30px;
      font-weight: bold;
      color: white;
    }}
    .green{{
    color: teal;
    font-size: 30px;
    font-weight: bold;
    }}
    .yellow{{
    color: rgb(147, 147, 20);
    font-size: 30px;
    font-weight: bold;
    }}
    .line{{
    background-color: teal;
    height: 2px;
    width: 100%;
    margin: 20px 0;
    }}
  </style>
</head>
<body>  <div class="box">
    <div class="container">
    <div class="flex">
      <div class="number">{car_info["ownership"]} owner</div>
      <div class="number">{car_info["colorOfCar"]}</div>
      <div class="number">{car_info["fuelType"]}</div>
    </div>
    <div class="flex2">
      <div class="left">
      <img src={image} alt="">
    </div>
    <div class="right">
      <div class="green">list price </div>
      <div class="yellow">Rs. {car_info["listPrice"]}</div>
      {offer_price_html}
    </div>
    </div>
  </div>
  </div>
</body>
</html>
    """
    return html_template

def frame4(car_info,image):
    html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Document</title>
  <style>
    *{{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    }}
    .box{{
      width: 100%;  
      height: 100vh;
      text-transform: uppercase;
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background-image: url('C:/Users/hp/NXcar/Video/bg.png');
      background-position: center;
      background-repeat: no-repeat;
      background-size: cover;
    }}
  
.heading{{
  border-top-right-radius: 12px;
  border-bottom-right-radius: 12px;

font-size: 30px;
font-weight: bold;
color: white;
background-color: teal;
width: max-content;
padding: 12px 20px;
}}
.flex{{
width: 100%;
display: flex;
justify-content: space-between;
align-items: flex-start;
}}
.right,
.left{{
width: 50%;
}}
.right{{
display: flex;
flex-direction: column;
justify-content: space-between;
}}
.flex2{{
width: 100%;
display: flex;
justify-content: space-between;
align-items: center;
margin-top: 30px;
}}
.field{{
  width: 100%;
  padding: 20px 0;
font-size: 25px;
font-weight: bold;
color: teal;
text-align: left;
}}
.image{{
  width:50%;
      padding: 0px;
      height: 400px;
      /* border: 1px solid red; */
      overflow: hidden;
      margin-top: -50px;
      margin-left: 50px;
      transform: scale(2);
}}
.image img{{
width: 100%;
      height: 600px;
    display: block;
    object-fit: contain;
}}
  </style>
</head>
<body>
  <div class="box">
        <div class="heading">vechile information</div>
        <div class="flex">
          <div class="left">
            <div class="flex2"> 
              <div class="field">Vehicle Number : </div>  
              <div class="field">{car_info['rc_report_generate']['regNo']}</div>  
            </div>
             <div class="flex2"> 
              <div class="field">Registration Authority : </div>  
              <div class="field">{car_info['rc_report_generate']['regAuthority']}</div>  
            </div>
             <div class="flex2"> 
              <div class="field">Registration Date : </div>  
              <div class="field">{car_info['rc_report_generate']['regDate']}</div>  
            </div>
             <div class="flex2"> 
              <div class="field">Vehicle Class : </div>  
              <div class="field">{car_info['rc_report_generate']['vehicleClass']}</div>  
            </div>
            <div class="flex2"> 
              <div class="field">Model : </div>  
              <div class="field">{car_info['rc_report_generate']['model']}</div>  
            </div>
          </div>
          <div class="right">
            <div>
              <div class="flex2"> 
              <div class="field">Vehicle Manufacturer Name :</div>  
              <div class="field">{car_info['rc_report_generate']['vehicleManufacturerName']}</div>  
            </div>
            <div class="flex2"> 
              <div class="field">Vehicle Colour : </div>  
              <div class="field">{car_info['rc_report_generate']['vehicleColour']}</div>  
            </div>
            </div>
            <div class="image">
              <img src={image} alt="">
            </div>
          </div>
        </div>
  </div>
</body>
</html>
    """
    return html_template

def frame5(image):
    html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    * {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}

    /* Main container with background image */
    .container {{
      width: 100%;
      height: 100vh;
      position: relative;
      display: flex;
      justify-content: center;
      align-items: flex-end; /* Make sure everything aligns at the bottom */
      background-image: url('C:/Users/hp/NXcar/Video/3d_bg.svg'); /* Placeholder, change to your background image */
      background-repeat: no-repeat;
      background-size: cover;
    }}

    /* Ground container for the car */
    .ground-container {{
      width: 100%;
      height: 10%; /* Adjust based on car height */
      display: flex;
      justify-content: center;
      align-items: flex-end; /* Align car at the bottom of the container */
      position: absolute;
      bottom: 0; /* Ensures the container is at the bottom of the screen */
    }}

    /* Car image settings */
    .image {{
      width:50%;
      padding: 0px;
      height: 470px;
      overflow: hidden;
      position: relative;
    }}

    .image img {{
      width: 100%;
      height: 450px; /* Keep the original aspect ratio */
      object-fit: contain; /* Ensure the car fits inside without distortion */
      display: block;
      /* box-shadow: 0 2px 2px 10px grey; */
        /* -webkit-box-reflect: below 0px
    linear-gradient(transparent, rgba(255, 255, 255, 0.5)); */
    }}

  </style>
  <title>3D Car Display</title>
</head>
<body>
  <div class="container">
    <!-- Ground container to hold the car image at the bottom -->
    <div class="ground-container">
      <div class="image">
        <img src={image} alt="Car Image">
      </div>
    </div>
  </div>
</body>
</html>

    """
    return html_template

# Function to remove the background from images after they are downloaded
def create_subtitle(text, start, end, video_size):
    font_size = 30
    font = ImageFont.truetype("arial.ttf", font_size)
    
    img = Image.new('RGBA', video_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    max_width = video_size[0] - 40
    lines = textwrap.wrap(text, width=int(max_width / (font_size * 0.6)))
    
    total_text_height = sum([draw.textbbox((0, 0), line, font=font)[3] for line in lines])
    background_height = int(1.5 * total_text_height)
    
    background_top = video_size[1] - background_height - 10
    background_bottom = video_size[1] - 10
    draw.rectangle([(0, background_top), (video_size[0], background_bottom)], fill="black")
    
    y_text = background_top + (background_height - total_text_height) // 2
    for line in lines:
        line_width, line_height = draw.textbbox((0, 0), line, font=font)[2:]
        text_position = ((video_size[0] - line_width) // 2, y_text)
        draw.text(text_position, line, font=font, fill="white")
        y_text += line_height
    
    return mp.ImageClip(np.array(img)).set_duration(end - start).set_start(start).set_end(end).set_position(("center", "bottom"))


def remove_background(image_path):
    output_path = "C:/Users/hp/NXcar/Video/image_no_bg.png"
    input_image = Image.open(image_path)
    # Remove the background
    output_image = remove(input_image)
    output_image = trim_image(output_image)
    # Save the output image
    output_image.save(output_path)
    return output_path

# Function to download images from the given URL and save them with specific names
def download_images(vehicle_number, image_links, folder_list):
    folder_name = f"images_{vehicle_number}"  # Folder for the specific vehicle number

    # Create folder if it doesn't exist
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    folder_list.append(folder_name)

    # Map the car sides to the corresponding image names
    image_mapping = {
        "Front": "1",
        "Front Left": "2",
        "Left Side": "3",
        "Back Left": "4",
        "Back": "5",
        "Back Right": "6",
        "Right Side": "7",
        "Front right": "8"
    }

    for link in image_links:
        try:
            # Extract the car side from the URL
            car_side = link.split('/')[-1].split('_')[0].replace('%20', ' ')
            if car_side in image_mapping:
                image_number = image_mapping[car_side]
                image_name = f"{image_number}.jpg"
                image_path = os.path.join(folder_name, image_name)

                # Download the image and save it
                img_data = requests.get(link).content
                with open(image_path, 'wb') as handler:
                    handler.write(img_data)
                print(f"Downloaded and saved {image_name} for {car_side}")

            else:
                print(f"Skipping unrecognized car side: {car_side}")

        except Exception as e:
            print(f"Error processing link: {link}, Error: {e}")
        

# Function to create subtitles for the video
def resize_image(image, target_size=(1920, 1080)):
    h, w = image.shape[:2]
    aspect = w / h

    # Calculate new dimensions to fit within the target size while maintaining aspect ratio
    if aspect > target_size[0] / target_size[1]:
        new_w = target_size[0]
        new_h = int(target_size[0] / aspect)
    else:
        new_h = target_size[1]
        new_w = int(target_size[1] * aspect)

    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # Create a canvas of the target size
    canvas = np.zeros((target_size[1], target_size[0], 3), dtype=np.uint8)

    # Center the resized image on the canvas
    y_offset = (target_size[1] - new_h) // 2
    x_offset = (target_size[0] - new_w) // 2

    # Ensure the new height and width fit within the target size
    canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized

    return canvas


# Function for creating a 3D video from images
def video_3d(image_folder, output_file, fps=30, video_duration=None):
    images = sorted(
        [os.path.join(image_folder, f) for f in os.listdir(image_folder) if f.endswith(('.jpg', '.jpeg', '.png'))],
        key=natural_sort_key
    )

    if not images:
        print("No images found in the specified folder.")
        return None

    print(f"Total images found: {len(images)}")

    valid_images = []
    for i, image_path in enumerate(images):
        frame = cv2.imread(image_path)
        if frame is None:
            print(f"Warning: Unable to read the image file: {image_path}")
        else:
            valid_images.append(image_path)

    if len(valid_images) == 0:
        print("No valid images found after filtering.")
        return None

    # Try to read the first image to get size
    first_image = cv2.imread(valid_images[0])
    height, width, layers = first_image.shape

    video_clips = []
    segment_duration = video_duration / (len(valid_images) + 1)

    for i, image_path in enumerate(valid_images):
        img = cv2.imread(image_path)
        if img is None:
            print(f"Error: Unable to read the image file: {image_path}")
            continue

        img_rgb = cv2.cvtColor(resize_image(img), cv2.COLOR_BGR2RGB)
        video_clips.append(mp.ImageClip(img_rgb).set_duration(segment_duration))

    # Append the first image at the end to create the 3D loop effect
    img = cv2.imread(valid_images[0])
    if img is None:
        print(f"Error: Unable to read the image file: {valid_images[0]}")
        return None
    img_rgb = cv2.cvtColor(resize_image(img), cv2.COLOR_BGR2RGB)
    video_clips.append(mp.ImageClip(img_rgb).set_duration(segment_duration))

    final_clip = mp.concatenate_videoclips(video_clips)
    return final_clip

# Function to create a video with images, audio, and optional 3D video generation
def create_video_from_images_and_audio(script, output_file,car_images, voice_id, captions, fps=30):
    image_folder = r"video_images"
    script_list = [item.strip() for item in script.split(';')]

    images = sorted([os.path.join(image_folder, f) for f in os.listdir(image_folder)
                     if f.lower().endswith(('.png', '.jpg', '.jpeg'))], key=natural_sort_key)

    if not images:
        print("No images found in the specified folder.")
        return

    # if (len(images) - 2) % 4 != 0 or len(script_list) != (len(images) // 4 + 2):
    #     print("Error: Mismatch between number of images and script segments.")
    #     return

    if not os.path.exists("temp_audio"):
        os.makedirs("temp_audio")

    audio_files = []
    for i, text in enumerate(script_list):
        audio_file = f"temp_audio/audio_{i}.mp3"
        text_to_speech(text, audio_file, voice_id)
        audio_files.append(audio_file)

    video_clips, subtitles, current_time = [], [], 0

    # Process first image
    img = cv2.imread(images[0])
    if img is None:
        print(f"Error: Unable to read the image file: {images[0]}")
        return

    img_rgb = cv2.cvtColor(resize_image(img), cv2.COLOR_BGR2RGB)
    audio = mp.AudioFileClip(audio_files[0])
    video_clips.append(mp.ImageClip(img_rgb).set_duration(audio.duration).set_audio(audio))
    subtitles.append(((current_time, current_time + audio.duration), script_list[0]))
    current_time += audio.duration

    # Process middle images and audio
    for i in range(1, len(script_list) - 1):
        audio = mp.AudioFileClip(audio_files[i])
        segment_duration = audio.duration / 4

        for j in range(4):
            img_index = 3 * (i - 1) + j + 1
            img = cv2.imread(images[img_index])
            if img is None:
                print(f"Error: Unable to read the image file: {images[img_index]}")
                continue

            if j == 3:
                # Call the 3D video function when j == 3
                print(f"Generating 3D video for segment {i} with j = 3")

                # Generate 3D video using images in the current vehicle folder
                image_folder_for_3d = car_images[i-1]  # Folder where images are stored
                duration_for_3d = segment_duration  # Duration for this segment in the main video

                # Create 3D video and append it to the main video clips
                video_3d_clip = video_3d(image_folder_for_3d, output_file, fps=fps, video_duration=duration_for_3d)
                video_3d_clip = video_3d_clip.set_audio(audio.subclip(j * segment_duration, (j + 1) * segment_duration))
                video_clips.append(video_3d_clip)
            else:
                # Process regular image and audio
                img_rgb = cv2.cvtColor(resize_image(img), cv2.COLOR_BGR2RGB)
                audio_part = audio.subclip(j * segment_duration, (j + 1) * segment_duration)
                video_clips.append(mp.ImageClip(img_rgb).set_duration(segment_duration).set_audio(audio_part))

        subtitles.append(((current_time, current_time + audio.duration), script_list[i]))
        current_time += audio.duration

    # Process last image
    img = cv2.imread(images[-1])
    if img is None:
        print(f"Error: Unable to read the image file: {images[-1]}")
        return

    img_rgb = cv2.cvtColor(resize_image(img), cv2.COLOR_BGR2RGB)
    audio = mp.AudioFileClip(audio_files[-1])
    video_clips.append(mp.ImageClip(img_rgb).set_duration(audio.duration).set_audio(audio))
    subtitles.append(((current_time, current_time + audio.duration), script_list[-1]))

    # Concatenate all clips
    final_clip = mp.concatenate_videoclips(video_clips)

    # Create subtitle clips and overlay on final clip
    if captions:
        subtitle_clips = [create_subtitle(text, start, end, final_clip.size) for (start, end), text in subtitles]
        final_clip = mp.CompositeVideoClip([final_clip] + subtitle_clips)

    # Write output video file
    final_clip.write_videofile(output_file, fps=fps, audio_codec="aac", codec="libx264")

    cleanup_temp_files(audio_files)
    print(f"Video created successfully: {output_file}")

# Cleanup temporary audio files
def cleanup_temp_files(audio_files):
    for audio_file in audio_files:
        try:
            os.remove(audio_file)
        except PermissionError:
            print(f"Could not remove {audio_file}. It may still be in use.")
    try:
        os.rmdir("temp_audio")
    except OSError:
        print("Could not remove temp_audio directory. It may not be empty.")

def text_to_speech(text, filename, voice_id):
    # Initialize the ElevenLabs client
    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

    response = client.text_to_speech.convert(
        voice_id=voice_id,
        optimize_streaming_latency="0",
        output_format="mp3_22050_32",
        text=text,
        model_id="eleven_multilingual_v2",  # use the turbo model for low latency
        voice_settings=VoiceSettings(
            stability=0.50,
            similarity_boost=.30,
            style=0.15,
            use_speaker_boost=True,
        ),
    )
    save_file_path = filename
    # Generating a unique file name for the output MP3 file
    # Writing the audio stream to the file
    with open(save_file_path, "wb") as f:
        for chunk in response:
            if chunk:
                f.write(chunk)


# Streamlit front-end
def main():
    st.title("Nexcar Video Script Generator")

    # Input vehicle numbers
    dealer_name = st.text_input("Enter Dealer Name")
    vehicle_numbers = st.text_input("Enter Vehicle Numbers (comma separated)")
    vehiclenumbers = [num.strip() for num in vehicle_numbers.split(',')]

    # Select language
    lang = st.radio("Select Script Language", ('English', 'Hindi'))

    # Option for captions
    captions = st.radio("Include Captions?", ('Yes', 'No')) == 'Yes'

    # Voice options (display name and corresponding voice_id)
    voices = {
        "Harry": "SOYHLrjzK2X1ezoPC6cr",
        "Thomas": "GBv7mTt0atIp3Br8iCZE",
        "Shrey": "IMzcdjL6UK1gZxag6QAU",
        "Raju": "zT03pEAEi0VHKciJODfn",
        "Leo": "IvLWq57RKibBrqZGpQrC",
        "Niraj": "zgqefOY5FPQ3bB7OZTVR",
        "Ranga": "d0grukerEzs069eKIauC",
        "Amit": "Sxk6njaoa7XLsAFT7WcN",
        "Aakash": "Uyx98Ek4uMNmWN7E28CD",
        "Anoop": "WyjIvPRJbxeuLCf0u23f",
        "Danish": "xZp4zaaBzoWhWxxrcAij",
        "Sachin": "XRdIKD2HKD2sMJjeC483",
        "Anand": "fKe9ZDqkOtN9VMLdbWJ5",
        "Faiq": "yDPEFTzp1EjwJuP2mt1k",
        "Vihan": "bUTE2M5LdnqaUCd5tJB3",
        "God": "ttpam6l3Fgkia7uX33b6",
        "Sohaib": "kLuXkg0zRFuSas1JFmMT",
        "Suhan": "JYesEroFZfIV2tXHwRem",
        "Kunal": "Qxb5zQvEo3DYQK2HNnXm",
        "Manu": "MUMZpJj46Atf8HF4CyAx",
        "Praveen": "v4ZRRmjvcrgAdi5qkWtZ",
        "Guru": "HP3OkBOPWanmqpjL7XVM"
    }

    # Select Voice
    selected_voice_name = st.radio("Select Voice for the Video", list(voices.keys()))

    # Get corresponding voice_id
    voice_id = voices[selected_voice_name]

    if st.button("Generate Script"):
        banner_image(vehiclenumbers[0])
        # Fetch car details
        # Initialize empty lists for car data
        distance, year, model, price = [], [], [], []
        for vehiclenumber in vehiclenumbers:
            car_info = carscope_details(vehiclenumber)
            if car_info:
                distance.append(car_info.get("kilometers", ""))
                model.append(car_info["rc_report_generate"]["model"])
                if car_info["offerPrice"]:
                    price.append(car_info["offerPrice"])
                else:
                    price.append(car_info["listPrice"])
                year.append(car_info["makeYear"].split('/')[1])
         
        # Create a formatted string for LLM prompt
        informative_c = []
        for i in range(len(vehiclenumbers)):
            car_details = f"Year: {year[i]}, Model: {model[i]}, Price: {price[i]} rupees, Distance: {distance[i]} km traveled"
            informative_c.append(car_details)

        informative_c_paragraph = "\n".join(informative_c)

        # Prepare the prompt based on language
        if lang == "English":
    # Improved Prompt for English Script Generation
            prompt = f"""You are a creative marketing scriptwriter with a deep understanding of the second-hand car market. Your task is to craft an engaging and persuasive script that will capture the attention of potential customers who are looking for reliable, certified pre-owned vehicles. The script should follow these guidelines:

            Start with the dealer's name, like '{dealer_name} presents Nexcar certified vehicles;'.
            Provide a separate line for each car, detailing the car's model, year, price, distance traveled, and any unique selling points.
            Use a semicolon (;) to separate each line.
            Write in full sentences that are clear, concise, and compelling.
            Make the script engaging by using formats like ₹8.25 lakhs and 70 thousand km.
            Include subtle calls to action in each line to encourage potential buyers.
            Emphasize the quality, value, and certification of these vehicles, making it clear that they are excellent choices for savvy buyers.
            End with a strong closing line highlighting the quality of the vehicles and encouraging customers to take advantage of the available services.
            The tone should be enthusiastic yet professional, aimed at building trust and excitement among potential buyers.
            Do not include any phrases like 'Here is the script:' or similar introductions.
            For example: 'Experience the thrill of driving a 2018 CRETA 1.6 CRDI AUTO SX+, packed with modern features and priced at just ₹8.25 lakhs, with only 70 thousand km on the clock;'.

            Here is the information you need to include:
            {informative_c_paragraph}

            Your goal is to make this script engaging, persuasive, and trust-building, effectively conveying the value of each vehicle to potential buyers.
            """

        else:
            prompt = f"""### **Prompt for Direct Hinglish Script Generation (More Engaging and Appealing):**

            "You are a creative marketing expert specializing in the Indian used car market. Your task is to craft an engaging and appealing script in Hinglish that will captivate potential buyers.

            **Instructions:**

            - The script should start with the dealer's name, "{dealer_name} lekar aaye hain aapke liye Nexcar certified gaadiyan;" and end with the fixed line, "Yeh gaadiyan Nexcar dwara inspect ki gayi hain aur bilkul badiya condition mein hain, aapke liye taiyaar. Avail kariye easy drive-away car loans, comprehensive insurance, extended warranty, aur RC transfer services Nexcar approved cars par. Aaj hi apni sapno ki gaadi ghar le jayein!"
            
            - **Content Structure:**
            - After the opening line, create compelling descriptions of each car that not only mention the car's name, price, distance traveled, and age but also include a catchy or emotional element that resonates with the buyer.
            - **Use an informal, conversational tone** that reflects excitement and a sense of urgency, encouraging the buyer to act quickly.
            - Use phrases like "sirf," "kam chalne wali," "ekdam mast condition mein," etc., to make the script feel more relatable and persuasive.
            - Mention the price and distance in a way that sounds attractive, e.g., "₹8.25 lakhs" as "sirf 8.25 lakhs mein" and "70 thousand km" as "70 hazaar km chali hui."
            - Each car description should be separated by a semicolon (;) and flow smoothly to the next without extra commentary.


            **Car Details to Include:**
            {informative_c_paragraph}

            **Output Expectations:**
            - The final script should be engaging, concise, and designed to appeal to Hinglish-speaking customers.
            - The tone should be lively and persuasive, creating a sense of urgency and excitement about the cars.
            - Do not include phrases like "Here is the script:", "Here is the generated Hinglish script for the vehicle promotion:" in the output."

            Remember to follow these instructions closely.
            """
        with st.spinner("Generating script..."):
            script = generate_script(prompt)

        # Display the generated script
        st.session_state['script'] = script
        st.session_state['script_generated'] = True

    # Display the generated script if available
    if st.session_state.get('script_generated', False):
        st.subheader("Generated Script")
        updated_script = st.text_area("Edit Script Below", st.session_state['script'], height=200, key='script_area')

        if st.button("Create Video"):
            with st.spinner('Generating video...'):
                # Create 
                vehicle_folders = []
                car_infos = []
                for vehiclenumber in vehiclenumbers:
                    car_info = carscope_details(vehiclenumber)
                    if car_info:
                        car_infos.append(car_info)
                    car_images = fetch_images(vehiclenumber)
                    if car_images and 'downloadLinks' in car_images:
                        print(f"Vehicle: {vehiclenumber}")           
                        # Step 1: Download the images
                        download_images(vehiclenumber, car_images['downloadLinks'], vehicle_folders)

                    else:
                        st.write("No image found for this vehicle.")

                output_file = "output_video.mp4"
                process_vehicle_images(vehicle_folders, car_infos)
                create_video_from_images_and_audio(updated_script, output_file,vehicle_folders, voice_id, captions)
            
            # Show the video
            st.video(output_file)

if __name__ == "__main__":
    main()
