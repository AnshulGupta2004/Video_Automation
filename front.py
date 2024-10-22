import xlsxwriter
import requests
import os
import streamlit as st
from PIL import Image, ImageChops
from rembg import remove
from dotenv import load_dotenv
from groq import Groq
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
import shutil

load_dotenv()

def clear_old_files(folder_path):
    if os.path.exists(folder_path):
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")

def download_and_save_images(vehicle_number, image_links):
    folder_name = f"car/{vehicle_number}"
    clear_old_files(folder_name)
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    image_mapping = {
        "Front Left": "1",
        "Left Side": "2",
        "Right Side": "3",
        "Front right": "4"
    }
    for link in image_links:
        try:
            car_side = link.split('/')[-1].split('_')[0].replace('%20', ' ')
            if car_side in image_mapping:
                image_number = image_mapping[car_side]
                image_name = f"{image_number}.png"
                image_path = os.path.join(folder_name, image_name)
                img_data = requests.get(link).content
                with open(image_path, 'wb') as handler:
                    handler.write(img_data)
                remove_background(image_path)
                print(f"Downloaded and saved {image_name} for {car_side}")
            else:
                print(f"Skipping unrecognized car side: {car_side}")
        except Exception as e:
            print(f"Error processing link: {link}, Error: {e}")

def trim_image(image):
    transparent_bg = Image.new("RGBA", image.size, (0, 0, 0, 0))
    bbox = ImageChops.difference(image, transparent_bg).getbbox()
    if bbox:
        return image.crop(bbox)
    return image

def remove_background(image_path):
    input_image = Image.open(image_path).convert("RGBA")
    output_image = remove(input_image)
    output_image = trim_image(output_image)
    output_image.save(image_path, "PNG")
    return image_path

def rc_detail(car_number):
    url = "https://crm.nxcar.in/api/driveaway_data"
    payload = {
        "vehiclenumber": car_number
    }
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        return None

def get_info(car_number):
    url = "https://crm.nxcar.in/api/fetchCarVideoImages"
    payload = {
        "vehiclenumber": car_number
    }
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()
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
        temperature=1.2
    )
    return response.choices[0].message.content.strip()

def text_to_speech(text, filename, voice_id):
    client = ElevenLabs(api_key=os.getenv("ELEVEN_LABS_API"))
    response = client.text_to_speech.convert(
        voice_id=voice_id,
        optimize_streaming_latency="0",
        output_format="mp3_22050_32",
        text=text,
        model_id="eleven_multilingual_v2",
        voice_settings=VoiceSettings(
            stability=0.50,
            similarity_boost=.30,
            style=0.15,
            use_speaker_boost=True,
        ),
    )
    with open(filename, "wb") as f:
        for chunk in response:
            if chunk:
                f.write(chunk)

def main():
    st.title("Nxcar Vehicle Promotion Script Generator")
    dealer_name = st.text_input("Enter Dealer Name:", "ABC Dealer")
    
    # Track vehicle numbers input
    vehicle_numbers_input = st.text_area("Enter Vehicle Numbers (comma separated):", key="vehicle_numbers_input")
    
    # Clear previous state when vehicle numbers input changes
    if 'last_vehicle_numbers_input' in st.session_state and st.session_state['last_vehicle_numbers_input'] != vehicle_numbers_input:
        st.session_state['scripts_generated'] = False  # Reset when vehicle numbers change
        st.session_state['audio_generated'] = False  # Reset generated audio when vehicle numbers change
    
    # Update the last input vehicle numbers
    st.session_state['last_vehicle_numbers_input'] = vehicle_numbers_input
    
    vehicle_numbers = [vn.strip() for vn in vehicle_numbers_input.split(',') if vn.strip()]
    intro_script = f"Discover Nxcar certified cars at {dealer_name}."
    updated_intro_script = st.text_area("Edit Intro Script", intro_script, height=50, key="intro_script_key")

    if st.button("Generate Scripts"):
        if 'scripts_generated' not in st.session_state or not st.session_state['scripts_generated']:
            workbook = xlsxwriter.Workbook('dealer_cars.xlsx')
            worksheet = workbook.add_worksheet()
            columns = [
                'Dealer Name', 'Make', 'Model Variant', 'Year', 'Distance',
                'Reg Date', 'List Price', 'Offer Price', 'Owner', 'Colour', 'Fuel',
                'Left Image', 'Right Image', 'Front-Right Image'
            ]
            for col_num, header in enumerate(columns):
                worksheet.write(0, col_num, header)
            row_index = 1
            scripts = {}
            for vehiclenumber in vehicle_numbers:
                car_info = get_info(vehiclenumber)
                if car_info and 'downloadLinks' in car_info:
                    print(f"Vehicle: {vehiclenumber}")
                    download_and_save_images(vehiclenumber, car_info['downloadLinks'])
                car_info = rc_detail(vehiclenumber)
                if car_info:
                    make = car_info.get('rc_report_generate', {}).get('vehicleManufacturerName', 'N/A')
                    model_variant = car_info.get('rc_report_generate', {}).get('model', 'N/A')
                    year = car_info.get("makeYear", "N/A").split("/")[-1]
                    distance = car_info.get("kilometers", 'N/A') + " Km"
                    reg_date = car_info.get('rc_report_generate', {}).get('regDate', 'N/A')
                    list_price = car_info.get("listPrice", 'N/A')
                    offer_price = car_info.get("offerPrice", 'N/A')
                    owner = str(car_info.get('ownership', 'N/A')) + " Owner"
                    colour = car_info.get('rc_report_generate', {}).get('vehicleColour', 'N/A')
                    fuel = car_info.get("fuelType", 'N/A')
                    data = [
                        dealer_name, make, model_variant, year, distance,
                        reg_date, list_price, offer_price, owner, colour, fuel,
                        f"car/{vehiclenumber}/2.png", f"car/{vehiclenumber}/3.png", f"car/{vehiclenumber}/4.png"
                    ]
                    for col_num, value in enumerate(data):
                        if col_num < len(columns) - 3:
                            worksheet.write(row_index, col_num, value)
                    image_paths = [
                        f"car/{vehiclenumber}/2.png",
                        f"car/{vehiclenumber}/3.png",
                        f"car/{vehiclenumber}/4.png"
                    ]
                    for i, path in enumerate(image_paths, start=11):
                        if os.path.exists(path):
                            worksheet.insert_image(row_index, i, path)
                        else:
                            print(f"Image not found: {path}")
                    prompt = f"""Get {make.split(" ")[0]} {model_variant} {year} with a price of {list_price} rupees only."""

                    scripts[vehiclenumber] = prompt
                    row_index += 1
            workbook.close()
            st.session_state['scripts'] = scripts
            st.session_state['dealer_name'] = dealer_name
            st.session_state['intro_script'] = updated_intro_script
            st.session_state['scripts_generated'] = True
            st.session_state['audio_generated'] = False
            st.success("Scripts generated successfully. You can now edit them. Just remove extra names in the variant like from Celerio VXI remove VXI.")

    if 'scripts' in st.session_state:
        st.header("Edit Generated Scripts")
        updated_scripts = {}
        for vehiclenumber, script in st.session_state['scripts'].items():
            updated_script = st.text_area(f"Script for vehicle {vehiclenumber}", script, height=100, key=f"script_{vehiclenumber}")
            # Check if script has changed
            if updated_script != script:
                st.session_state['audio_generated'] = False  # Reset audio generation if script is updated
            updated_scripts[vehiclenumber] = updated_script
        st.session_state['scripts'] = updated_scripts

        if st.button("Generate Audio Files") and not st.session_state.get('audio_generated', False):
            output_folder = "output_audio"
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
            else:
                clear_old_files(output_folder)
            for vehiclenumber, script in updated_scripts.items():
                car_info = rc_detail(vehiclenumber)
                model_variant = car_info.get('rc_report_generate', {}).get('model', vehiclenumber) if car_info else vehiclenumber
                tts_filename = f"{output_folder}/{model_variant}_script.mp3"
                text_to_speech(script, tts_filename, voice_id="bUTE2M5LdnqaUCd5tJB3")
            intro_filename = f"{output_folder}/intro_script.mp3"
            text_to_speech(st.session_state['intro_script'], intro_filename, voice_id="bUTE2M5LdnqaUCd5tJB3")
            st.session_state['audio_generated'] = True
            st.success("Audio files generated successfully.")

    # Ensure the download button for the Excel file is always visible after scripts are generated
    if 'scripts_generated' in st.session_state and st.session_state['scripts_generated']:
        with open("dealer_cars.xlsx", "rb") as f:
            st.download_button("Download Excel File", f, file_name="dealer_cars.xlsx")

    if st.session_state.get('audio_generated', False):
        output_folder = "output_audio"
        for file in os.listdir(output_folder):
            if file.endswith(".mp3"):
                with open(os.path.join(output_folder, file), "rb") as f:
                    st.download_button(f"Download {file}", f, file_name=file)

if __name__ == "__main__":
    main()
