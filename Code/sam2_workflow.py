import tkinter as tk
from tkinter import ttk, filedialog
import observation_management
from sam2_class import Sam
from json_read_write import JsonReadWrite 
from frame_info_struct import FrameInfoStruct 
from further_extract_frames import LoadMoreFrames
import os
import threading
from PIL import Image, ImageTk, ImageDraw
from annotation_window import AnnotationWindow
import cv2
import numpy as np


class ImageDisplayApp(tk.Tk):
    def __init__(self, frame_dir = None, video_path = None, frame_rate = None, window_title = "Image Grid Display with Input Field", schadens_kurzel = None, stop_callback=None):
        super().__init__()

        self.title(window_title)
        self.geometry("1200x1000")
        self.images = []
        self.image_paths = []
        self.initialized = False
        self.video_path = video_path
        self.checkbox_vars = {}
        self.stop_callback = stop_callback

        # Stores the observations
        self.observations = observation_management.RadioButtonManagement()     

        # Saves Frame information, like the names, filepaths and so on
        self.frame_info = FrameInfoStruct(frame_dir)
        # Manages extraction of further frames on basis of Frame info
        self.frame_extraction = LoadMoreFrames(self.frame_info)

        # Loads and interacts with the SAM2 segmentation model
        self.sam_model = Sam(frame_dir)
        self.object_class_id = 0

        # Initializes the json storage file and reads it, if it exists
        json_path =  os.path.join(self.frame_info.working_dir, f"{str(os.path.basename(self.frame_info.working_dir))}.json")
        self.json = JsonReadWrite(json_path)
        
        if not self.json.get_json():
            self.observations.add_observation(schadens_kurzel)
            self.json.prepare_json_with_frames(self.frame_info.get_frame_name_list(), self.observations.get_observation_list())
        else:
            self.check_json_for_observations()




        # Radiobutton variable to store the selected option
        self.radio_var = tk.StringVar()
        
        # Frame for Radiobuttons and input field
        radio_frame = tk.Frame(self)
        radio_frame.pack(side="top", fill="x", padx=10, pady=5)

        # Add widgets in the radio_frame horizontally
        tk.Label(radio_frame, text="Add option:").pack(side="left", padx=(0, 5))
        self.new_option_entry = tk.Entry(radio_frame, width=15)
        self.new_option_entry.pack(side="left", padx=(0, 5))

        # Add button
        add_button = ttk.Button(radio_frame, text="Add", command=self.read_option_and_clear_entry_field)
        add_button.pack(side="left", padx=(5, 0))

        # Radiobuttons container
        self.radio_container = tk.Frame(radio_frame)
        self.radio_container.pack(side="left", padx=10, pady=5)

        self.wait_label = tk.Label(radio_frame, text="", font=("Helvetica", 16), fg="red")
        self.wait_label.pack(side="left", padx=10, pady=5)

        # Button to delete labeling
        self.more_images_forward = ttk.Button(radio_frame, text="delete unselected labels", command=self.delete_damage)
        self.more_images_forward.pack(side="left", padx=(5, 5))

        # Button to skip to next label
        self.more_images_forward = ttk.Button(radio_frame, text="Next", command=self.destroy)
        self.more_images_forward.pack(side="right", padx=(5, 5))

        # Button to stop labeling
        self.more_images_forward = ttk.Button(radio_frame, text="Cancel", command=self.stop_program)
        self.more_images_forward.pack(side="right", padx=(5, 5))

        # Initialize canvas
        self.canvas = tk.Canvas(self, width=1000, height=800, bg="white")
        self.canvas.pack(fill="both", expand=True)

        # Frame to hold the input field, button, and directory selection
        input_frame = tk.Frame(self)
        input_frame.pack(side="top", fill="x", padx=10, pady=5)

        # Add Previous and Next buttons to navigate images
        self.prev_button = ttk.Button(input_frame, text="<", command=self.prev_images)
        self.prev_button.pack(side="left", padx=(5, 0))

        self.next_button = ttk.Button(input_frame, text=">", command=self.next_images)
        self.next_button.pack(side="left", padx=(5, 0))

        # Short slider (10% of the window width)
        self.image_slider = ttk.Scale(input_frame, from_=0, to=0, orient="horizontal", command=self.slider_update)
        self.image_slider.pack(side="left", fill="x", expand=False, padx=(10, 5), ipadx=12)  # Adjust width with ipadx

        # Label
        tk.Label(input_frame, text="Grid Size:").pack(side="left", padx=(0, 5))

        # Entry field with specified width
        self.grid_entry = tk.Entry(input_frame, width=10)  # Set the width here
        self.grid_entry.insert(0, "5")
        self.grid_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        # Button for updating grid
        self.button = ttk.Button(input_frame, text="Update Grid", command=self.reload_grid_and_images)
        self.button.pack(side="left", padx=(5, 0))

        self.more_images_back = ttk.Button(input_frame, text="extract previous images", command=lambda: self.extract_images(self.video_path, forwards=False))
        self.more_images_back.pack(side="left", padx=(5, 0))

        self.more_images_forward = ttk.Button(input_frame, text="extract next images", command=lambda: self.extract_images(self.video_path, forwards=True))
        self.more_images_forward.pack(side="left", padx=(5, 0))

    def extract_images(self, video_path, forwards):
        if self.initialized:
            popup = tk.Toplevel()
            popup.title("Processing")

            label = tk.Label(popup, text="Frames are being extracted...")
            label.pack(padx=20, pady=10)

            # Create a progress bar
            progress = ttk.Progressbar(popup, orient="horizontal", length=300, mode="indeterminate")
            progress.pack(pady=10)
            progress.start()  # Start the progress bar animation

            def extraction():
                if forwards:
                    self.frame_extraction.extract_forwards(video_path, 10)
                else:
                    self.frame_extraction.extract_backwards(video_path, 10)
                    
                popup.destroy()  # Close the pop-up after the function finishes

            # Run the task in a separate thread
            threading.Thread(target=extraction).start()

            self.init_sam_with_selected_observation()
            self.reload_grid_and_images()

    def read_option_and_clear_entry_field(self):
        # Callback für den Button, um die neue Option hinzuzufügen.
        self.observations.add_observation(self.new_option_entry.get().strip())
        self.new_option_entry.delete(0, "end")
        self.update_observation_radiobuttons()
        

    def update_obj_id_to_selected_observation(self):
        selected_option = self.radio_var.get()
        observation_list = self.observations.get_observation_list()
        if selected_option in observation_list:
            self.object_class_id = observation_list.index(selected_option)
        else:
            self.object_class_id = 0

    def check_json_for_observations(self):
        json_data = self.json.get_json()
        observation_list = self.observations.get_observation_list()
        for frame in json_data.keys():
            observation = json_data[frame]["Observations"]
            for key in observation.keys():
                if key not in observation_list:
                    observation_list.append(key)
                    self.observations.add_observation(key)

    def update_observation_radiobuttons(self):
        # Define the colors for the radio buttons (matching overlay colors)
        colors = [
            (255, 100, 100),   # Red
            (100, 100, 255),   # Blue
            (100, 255, 100),   # Green
            (255, 255, 100),   # Yellow
            (255, 100, 255)    # Magenta
        ]

        # Clear existing radio buttons
        for widget in self.radio_container.winfo_children():
            widget.destroy()

        # Reset Checkbox_vars
        self.checkbox_vars = {}

        observation_list = self.observations.get_observation_list()
        # Create the Radiobuttons in a horizontal layout
        for index, option in enumerate(observation_list):
            # Get the color based on the index and rotate it if there are more options than colors
            color = colors[index % len(colors)]
            color_hex = "#{:02x}{:02x}{:02x}".format(*color)  # Convert RGB to hex

            # Create a frame for each radio button and checkbox
            frame = tk.Frame(self.radio_container)
            frame.pack(side="left", padx=5)

            # Create the radio button
            rb = tk.Radiobutton(frame, text=option, variable=self.radio_var, value=option, bg="white", command=self.radio_button_value_changed)
            rb.pack()

            # Create a Checkbutton below each Radiobutton
            check_var = tk.BooleanVar(value=True)  # Set to True initially (checked)
            checkbox = tk.Checkbutton(frame, variable=check_var, bg=color_hex, command=self.show_selected_images)
            checkbox.pack()

            # Store the check_var in a dictionary with the option as the key
            self.checkbox_vars[option] = check_var

        # Set the default selection to the first option
        if observation_list:
            self.radio_var.set(observation_list[0])

    def delete_damage(self):
        to_delete_list = []
        observation_list = self.observations.get_observation_list()
        for observation in observation_list:
            if not self.checkbox_vars[observation].get():
                to_delete_list.append(observation)

        self.observations.remove_observations(to_delete_list)
        self.json.remove_damages_from_json(to_delete_list)
        self.json.load_json_from_file()
        self.update_observation_radiobuttons()
        self.reload_grid_and_images()

    def stop_program(self):
        """Function to stop the program and signal the loop to exit."""
        if self.stop_callback:
            self.stop_callback()  # Call the stop callback to stop the loop
        self.destroy()

    def radio_button_value_changed(self):
        self.update_obj_id_to_selected_observation()
        self.init_sam_with_selected_observation()

    def init_sam_with_selected_observation(self):
        points_dict = self.get_points_for_selected_observations()   # load points for selected observation from json
        self.sam_model.reset_predictor_state()   # reset sam state and add new points

        if points_dict:
            self.add_new_points_to_sam(points_dict)

    def add_new_points_to_sam(self, points_dict):
        for points_labels_and_frame_index in points_dict.values(): 
            self.sam_model.add_point(points_labels_and_frame_index, self.object_class_id)

    def get_points_for_selected_observations(self):
        points_dict = dict()
        json_data = self.json.get_json()
        sel_observation = self.radio_var.get()

        if len(json_data) == 0:
            return None
        
        for frame_number, frame_data in json_data.items():
            observations = frame_data["Observations"]
            if sel_observation not in observations:
                continue

            kuerzel_data = observations[sel_observation]
            
            points_list = []
            labels_list = []
            frame_name = frame_data["File Name"]

            if "Punkte" not in kuerzel_data:
                continue

            pos_points = kuerzel_data["Punkte"].get("1", [])
            neg_points = kuerzel_data["Punkte"].get("0", [])
            
            for punkt in pos_points:
                points_list.append(punkt)
                labels_list.append(1)

            for punkt in neg_points:
                points_list.append(punkt)
                labels_list.append(0)

            frame_list = self.frame_info.get_frame_name_list()
            img_index = frame_list.index(frame_name)

            points_dict[frame_number] = {"Image Index" : img_index,
                                        "Punkte" : points_list,
                                        "Labels" : labels_list
                                        }
            
        if len(points_dict) < 0:
            return None
                
        return points_dict

    def reload_grid_and_images(self):
        self.update_observation_radiobuttons()
        grid_size = int(self.grid_entry.get())

        if grid_size > 1:
            print(f"Grid size = {grid_size}")

            images_per_grid = grid_size * grid_size
            slider_max = max(0, len(self.frame_info.get_frame_name_list()) - images_per_grid)
            self.image_slider.config(from_=0, to=slider_max)

            self.show_selected_images(0)
        
    def get_canvas_info(self):
        # Get canvas size
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width <= 0 or canvas_height <= 0:
            return

        try:
            grid_size = int(self.grid_entry.get())
        except ValueError:
            print("Invalid input. Please enter a valid integer.")
            return

        if grid_size <= 0:
            return

        cell_width = canvas_width / grid_size
        cell_height = canvas_height / grid_size

        return cell_width, cell_height, grid_size

    def show_selected_images(self, start_index = None):
        """Displays images in a grid format on the canvas."""
        if not self.initialized:
            return
        
        if not start_index:
            start_index = self.image_slider.get()

        self.image_refs = []


        image_list = self.frame_info.get_frames()
        image_names = self.frame_info.get_frame_name_list()

        self.canvas.delete("all")
        cell_width, cell_height, grid_size = self.get_canvas_info()

        json_data = self.json.get_json()

        for i in range(grid_size * grid_size):
            index = start_index + i

            if index >= len(image_list):
                break

            img = image_list[index]
            img_name = image_names[index]

            # Add mask if available
            if json_data:
                for frame in json_data.values():
                    if img_name in frame["File Name"]:
                        
                        masked_img = self.draw_mask_on_image(img, frame)
                        img = masked_img

            # Resize the image
            img = img.resize((int(cell_width), int(cell_height)), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)

            self.image_refs.append(tk_img)

            # Place the image on the canvas
            row = i // grid_size
            col = i % grid_size
            x_position = col * cell_width
            y_position = row * cell_height
            self.canvas.create_image(x_position + cell_width // 2, y_position + cell_height // 2, image=tk_img)

    def draw_mask_on_image(self, img, frame):
        # Define a set of colors for different mask.json files
        colors = [
            (255, 0, 0, 100),   # Red with transparency
            (0, 0, 255, 100),   # Blue with transparency
            (0, 255, 0, 100),   # Green with transparency
            (255, 255, 0, 100), # Yellow with transparency
            (255, 0, 255, 100)  # Magenta with transparency
        ]

        observation_list = self.observations.get_observation_list()

        for kuerzel in observation_list:
            # Create a transparent overlay for polygons
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay, "RGBA")

            if kuerzel in frame["Observations"]:
                schaden_data = frame["Observations"][kuerzel]

                if schaden_data.keys() is None:
                    continue
                # Check if "Maske" exists
                if "Maske" in schaden_data:
                    polygons = schaden_data["Maske"]
                else:
                    polygons = None

                # Check if "Punkte" exists
                if "Punkte" in schaden_data:
                    points = schaden_data["Punkte"]
                    pos_points = points.get("1", [])
                    neg_points = points.get("0", [])
                else:
                    pos_points = None
                    neg_points = None

                observation_index = observation_list.index(kuerzel)
                color = colors[observation_index % len(colors)]

                if self.checkbox_vars[kuerzel].get():
                    # Draw polygons
                    if polygons:
                        for polygon in polygons:
                            polygon_tuples = [tuple(point) for point in polygon]
                            if len(polygon_tuples) > 3:
                                overlay_draw.polygon(polygon_tuples, outline=color[:3], fill=color)

                    # Draw positive points (green circles)
                    if pos_points:
                        for point in pos_points:
                            x, y = point
                            radius = 5
                            overlay_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(0, 255, 0, 255))

                    # Draw negative points (red circles)
                    if neg_points:
                        for point in neg_points:
                            x, y = point
                            radius = 5
                            overlay_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(255, 0, 0, 255))

            # Composite the overlay with the original image
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            img = Image.alpha_composite(img, overlay)
            img = img.convert("RGB")

        return img

    def slider_update(self, current_index):
        """Update image display when the slider is moved."""
        #current_index = self.image_slider.get()
        self.show_selected_images(int(float(current_index)))

    def prev_images(self):
        """Go to the previous set of images."""
        grid_size = int(self.grid_entry.get())
        current_index = self.image_slider.get()
        new_index = int(max(0, current_index - grid_size))
        self.show_selected_images(new_index)
        self.image_slider.set(new_index)  # Update slider

    def next_images(self):
        """Go to the next set of images."""
        grid_size = int(self.grid_entry.get())
        images_per_grid = grid_size * grid_size
        current_index = self.image_slider.get()
        max_value = len(self.frame_info.get_frame_name_list()) - images_per_grid
        new_index = int(min(max_value, current_index + grid_size))
        self.show_selected_images(new_index)
        self.image_slider.set(new_index)  # Update slider
 
    def on_canvas_click(self, event):

        """Handle mouse click events on the canvas."""
        x, y = event.x, event.y

        print("clicked")
        cell_width , cell_height, grid_size = self.get_canvas_info()

        row = int(y // cell_height)
        col = int(x // cell_width)

        start_index = int(self.image_slider.get())

        # Calculate the index of the clicked image
        index = row * grid_size + col + start_index

        print(f"index {index}")
        # Open the selected image in a new window and add points
        self.open_annotation_window_save_Coordinates(index)

        self.multithread_sam_progressbar()
        self.reload_grid_and_images()

    def multithread_sam_progressbar(self):
        popup = tk.Toplevel()
        popup.title("Processing")
        label = tk.Label(popup, text="Objects are being tracked...")
        label.pack(padx=20, pady=10)
        popup.grab_set()

        # Create a progress bar
        progress = ttk.Progressbar(popup, orient="horizontal", length=300, mode="indeterminate")
        progress.pack(pady=10)
        progress.start()  # Start the progress bar animation

        def sam_thread():
            self.track_object()
            popup.destroy()  # Close the pop-up after the function finishes

        # Run the task in a separate thread
        threading.Thread(target=sam_thread).start()
        self.wait_window(popup)
        
    def open_annotation_window_save_Coordinates(self, img_index):
        annotation_window = tk.Toplevel(self)
        annotation_window.title(f"Punkte für {self.radio_var.get()} hinzufügen")
        shown_frames = self.frame_info.get_frames()

        annotation_window.grab_set()
        window = AnnotationWindow(annotation_window, shown_frames[img_index], img_index, self.object_class_id, self.sam_model)

        self.wait_window(annotation_window)
        print("window closed")


        # Save Coordinates
        points, labels, polygons = window.get_points_and_labels()

        if len(points) > 0 and len(points) == len(labels):
            self.add_info_to_json(img_index, polygons, points, labels)

    def add_info_to_json(self, img_index, polygons, points = None, labels = None, label_index = None):
        pos_points = []
        neg_points = []

        if points is not None:
            for coordinates, label in zip(points, labels):
                if label == 1:
                    pos_points.append(coordinates)
                elif label == 0:
                    neg_points.append(coordinates)

        all_frames = self.frame_info.get_frame_name_list()
        frame_name = all_frames[img_index]
        observation = self.radio_var.get()


        if points is not None:
            self.json.add_frame_to_json(frame_name=frame_name,
                                        observation=observation,
                                        polygons=polygons,
                                        pos_points=pos_points,
                                        neg_points=neg_points,
                                        sequence_index=label_index)
        else:
            self.json.add_frame_to_json(frame_name=frame_name,
                                        observation=observation,
                                        polygons=polygons)
        self.json.save_json_to_file()

    def track_object(self):
        video_segments = self.sam_model.propagate_in_video()

        for out_frame_idx, masks in video_segments.items():
            
            mask_data = []

            for out_obj_id, out_mask in masks.items():
                # Remove singleton dimensions
                out_mask = np.squeeze(out_mask)  # Squeeze to remove dimensions of size 1
                
                # Extract contours using OpenCV
                contours, _ = cv2.findContours(out_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                for contour in contours:
                    # Simplify the contour using approxPolyDP
                    epsilon = 0.0005 * cv2.arcLength(contour, True)  # Adjust epsilon for simplification level
                    simplified_contour = cv2.approxPolyDP(contour, epsilon, True)

                    # Convert contour points to a list of tuples
                    simplified_contour = [(int(point[0][0]), int(point[0][1])) for point in simplified_contour]
                    
                    mask_data.append(simplified_contour)

            self.add_info_to_json(out_frame_idx, mask_data)
        
        self.json.save_json_to_file()

    def run(self):
        """Start the Tkinter event loop."""
        self.initialized = True
        self.init_sam_with_selected_observation()
        self.canvas.bind("<Button-1>", self.on_canvas_click)  # Bind left click to canvas
        self.canvas.bind("<Button-3>", self.on_canvas_click)  # Bind right click to canvas
        
        self.state("zoomed")    
        self.update_idletasks()
        self.update()
        self.reload_grid_and_images()
        self.mainloop()

if __name__ == "__main__":
    app = ImageDisplayApp(frame_dir = r"C:\Users\K3000\Videos\SAM2 Tests\KI_1", schadens_kurzel = "BBA", video_path=r"C:\Users\K3000\Videos\SAM2 Tests\KI_1.MPG")
    app.run()
