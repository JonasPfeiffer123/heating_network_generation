# Calculation modell for STES (Seasonal Thermal Energy Storage) systems
"""
DATE: 02.10.2024
AUTHOR: Dipl-Ing. (FH) Jonas Pfeiffer
FILENAME: STES.py

Calculation model for STES (Seasonal Thermal Energy Storage) systems.

Calculation model source:
Simulation method for assessing hourly energy flows in district heating system with seasonal thermal energy storage
Authors: Kapil Narula, Fleury de Oliveira Filho, Willy Villasmil, Martin K. Patel
Link: https://www.sciencedirect.com/science/article/pii/S0960148119318154?via%3Dihub
"""

### Reihenfolge muss geändert werden: Oben beladen, unten entladen
### Darstellung der Temperaturverteilung in 3D als Zylinder oder Rechteck nicht nur als Kreisringe

import os
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.widgets import Slider, Button
from matplotlib.animation import FuncAnimation
from scipy.optimize import minimize

# Globals for animation control
is_animating = False
anim_speed = 200  # Default animation speed (in ms per frame)
anim = None  # Holds the FuncAnimation instance
current_frame = 0  # Tracks the current frame

def update_plot(val, storage, ax):
    """Update the 3D plot based on the selected time step from the slider."""
    global current_frame
    current_frame = int(val)  # Set the current frame to the slider value
    ax.cla()  # Clear the axis
    storage.plot_3d_temperature_distribution(ax, current_frame)  # Plot for the given time step
    ax.set_title(f'Temperature Stratification (Time Step {current_frame})')
    plt.draw()  # Redraw the figure

def animate(i, storage, ax):
    """Animation function to update the plot at each time step."""
    global current_frame
    ax.cla()  # Clear the axis
    storage.plot_3d_temperature_distribution(ax, i)  # Plot for the given time step
    ax.set_title(f'Temperature Stratification (Time Step {i})')
    current_frame = i
    slider.set_val(i)  # Update slider position to reflect the current time step
    return ax,

def start_animation(storage, ax):
    """Start the animation."""
    global anim, is_animating
    if not is_animating:
        anim = FuncAnimation(fig, animate, frames=storage.hours, fargs=(storage, ax),
                             interval=anim_speed, blit=False, repeat=True)
        is_animating = True
        plt.draw()

def stop_animation():
    """Stop the animation."""
    global anim, is_animating
    if anim is not None:
        anim.event_source.stop()  # Stop the animation
        is_animating = False

def forward(storage):
    """Move forward by 1 frame."""
    global current_frame
    current_frame = min(current_frame + 1, storage.hours - 1)  # Increment the frame
    slider.set_val(current_frame)  # Update slider to the new frame

def backward():
    """Move backward by 1 frame."""
    global current_frame
    current_frame = max(current_frame - 1, 0)  # Decrement the frame
    slider.set_val(current_frame)  # Update slider to the new frame

def adjust_speed(val, storage):
    """Adjust the animation speed based on the speed slider."""
    global anim_speed
    anim_speed = int(val)  # Update the speed
    if is_animating:
        stop_animation()  # Restart the animation with the new speed
        start_animation(storage, ax)

def interactive_plot(storage):
    storage.labels_exist = False  # Reset the labels flag
    storage.colorbar_exists = False  # Reset the color bar flag
    """Create an interactive plot with a slider, start/stop buttons, and speed control."""
    global fig, ax, slider
    fig, ax = plt.subplots(subplot_kw={"projection": "3d"})
    plt.subplots_adjust(left=0.1, bottom=0.35)
    
    # Initial plot
    storage.plot_3d_temperature_distribution(ax, current_frame)
    
    # Add time step slider
    ax_slider = plt.axes([0.1, 0.1, 0.65, 0.03], facecolor='lightgoldenrodyellow')
    slider = Slider(ax_slider, 'Time Step', 0, storage.hours - 1, valinit=current_frame, valstep=1)
    
    # Update plot when slider is changed
    slider.on_changed(lambda val: update_plot(val, storage, ax))
    
    # Add start button
    ax_start = plt.axes([0.1, 0.25, 0.1, 0.04])
    start_button = Button(ax_start, 'Start', color='lightblue', hovercolor='green')
    start_button.on_clicked(lambda event: start_animation(storage, ax))
    
    # Add stop button
    ax_stop = plt.axes([0.25, 0.25, 0.1, 0.04])
    stop_button = Button(ax_stop, 'Stop', color='lightblue', hovercolor='red')
    stop_button.on_clicked(lambda event: stop_animation())
    
    # Add forward button
    ax_forward = plt.axes([0.4, 0.25, 0.1, 0.04])
    forward_button = Button(ax_forward, 'Forward', color='lightblue', hovercolor='yellow')
    forward_button.on_clicked(lambda event: forward(storage))
    
    # Add backward button
    ax_backward = plt.axes([0.55, 0.25, 0.1, 0.04])
    backward_button = Button(ax_backward, 'Backward', color='lightblue', hovercolor='yellow')
    backward_button.on_clicked(lambda event: backward())
    
    # Add speed control slider
    ax_speed = plt.axes([0.75, 0.25, 0.15, 0.04])
    speed_slider = Slider(ax_speed, 'Speed (ms)', 50, 1000, valinit=anim_speed)
    speed_slider.on_changed(lambda val: adjust_speed(val, storage))
    
    plt.show()

class ThermalStorage:
    def __init__(self, storage_type, dimensions, rho, cp, T_ref, lambda_top, lambda_side, lambda_bottom, lambda_soil, 
                 T_amb, T_soil, T_max, T_min, initial_temp, dt_top, ds_side, db_bottom, hours=8760, num_layers=5, thermal_conductivity=0.6):
        self.storage_type = storage_type
        self.dimensions = dimensions
        self.rho = rho
        self.cp = cp
        self.T_ref = T_ref
        self.lambda_top = lambda_top
        self.lambda_side = lambda_side
        self.lambda_bottom = lambda_bottom
        self.lambda_soil = lambda_soil
        self.T_amb = T_amb
        self.T_soil = T_soil
        self.T_max = T_max
        self.T_min = T_min
        self.dt_top = dt_top  # Thickness of the top insulation
        self.ds_side = ds_side  # Thickness of the side insulation
        self.db_bottom = db_bottom  # Thickness of the bottom insulation
        self.hours = hours
        
        self.num_layers = num_layers  # Number of layers for stratified storage
        self.thermal_conductivity = thermal_conductivity  # W/m*K thermal conductivity of the medium
        self.Q_sto = np.zeros(hours)  # Stored heat in J
        self.Q_loss = np.zeros(hours)  # Heat loss in kW
        self.T_sto = np.zeros(hours)  # Storage temperature in °C
        self.T_sto[0] = initial_temp  # Initial storage temperature in °C
        
        # Surface areas and volume depend on the geometry
        if storage_type == "cylindrical":
            self.volume, self.S_top, self.S_side, self.S_bottom = self.calculate_cylindrical_geometry(dimensions)
        elif storage_type == "truncated_cone":
            self.volume, self.S_top, self.S_side, self.S_bottom = self.calculate_truncated_cone_geometry(dimensions)
        elif storage_type == "truncated_trapezoid":
            self.volume, self.S_top, self.S_side, self.S_bottom = self.calculate_truncated_trapezoid_geometry(dimensions)
        else:
            raise ValueError("Unsupported storage type")

        self.colorbar_exists = False  # Track if the color bar has already been added
        self.labels_exist = False  # Track if the labels have been set
    
    def calculate_cylindrical_geometry(self, dimensions):
        """Calculate surface areas and volume for cylindrical storage."""
        radius, height = dimensions
        volume = np.pi * radius**2 * height  # Volume of the cylinder
        S_top = np.pi * radius**2  # Surface area of the top/bottom
        S_side = 2 * np.pi * radius * height  # Surface area of the side
        return volume, S_top, S_side, S_top  # Same surface area for top and bottom

    # PTES: Pit Thermal Energy Storage (Truncated Cone)
    def calculate_truncated_cone_geometry(self, dimensions):
        """Calculate surface areas and volume for a truncated cone PTES."""
        top_radius, bottom_radius, height = dimensions
        # Volume of the truncated cone
        volume = (1/3) * np.pi * height * (top_radius**2 + bottom_radius**2 + top_radius * bottom_radius)
        
        # Surface areas
        S_top = np.pi * top_radius**2  # Surface area of the top
        S_bottom = np.pi * bottom_radius**2  # Surface area of the bottom
        
        # Slant height for the side area calculation
        slant_height = np.sqrt((top_radius - bottom_radius)**2 + height**2)
        
        # Side surface area of the truncated cone
        S_side = np.pi * (top_radius + bottom_radius) * slant_height
        
        return volume, S_top, S_side, S_bottom

    # PTES: Pit Thermal Energy Storage (Truncated Trapezoid)
    def calculate_truncated_trapezoid_geometry(self, dimensions):
        """Calculate surface areas and volume for a truncated trapezoid PTES."""
        top_length, top_width, bottom_length, bottom_width, height = dimensions
        
        # Calculate the volume of the truncated trapezoid
        A_top = top_length * top_width  # Area of the top rectangle
        A_bottom = bottom_length * bottom_width  # Area of the bottom rectangle
        volume = (1/3) * height * (A_top + A_bottom + np.sqrt(A_top * A_bottom))
        
        # Side surface areas (trapezoidal faces)
        side_length = np.sqrt((top_length - bottom_length)**2 + height**2)
        side_width = np.sqrt((top_width - bottom_width)**2 + height**2)
        
        S_side_length = (top_length + bottom_length) * side_length / 2  # Trapezoidal area along the length
        S_side_width = (top_width + bottom_width) * side_width / 2  # Trapezoidal area along the width
        
        # Top and bottom surface areas
        S_top = top_length * top_width
        S_bottom = bottom_length * bottom_width
        
        # Total side surface area
        S_side = 2 * (S_side_length + S_side_width)
        
        return volume, S_top, S_side, S_bottom
   
    def calculate_heat_loss(self, T_sto_last):
        if self.storage_type == "cylindrical_overground":
            # Loss from top
            Q_t = (T_sto_last - self.T_amb) * (self.lambda_top / self.dt_top) * self.S_top
            # Loss from sides
            Q_s = (T_sto_last - self.T_amb) * (self.lambda_side / self.ds_side) * self.S_side
            # Loss from bottom
            Q_b = (T_sto_last - self.T_amb) * (self.db_bottom / self.lambda_bottom + 4 * self.dimensions[0] / (3 * np.pi * self.lambda_soil))**(-1) * self.S_bottom
            return (Q_t + Q_s + Q_b) / 1000  # Convert to kW

        elif self.storage_type == "cylindrical_underground":
            # Loss from sides and bottom combined
            R = self.dimensions[0]
            H = self.dimensions[1]
            d_min = (self.lambda_side / self.lambda_soil) * R * 0.37
            if self.ds_side > 2 * d_min:
                K_sb = (self.ds_side / self.lambda_side + 0.52 * R / self.lambda_soil)**(-1)
            else:
                raise ValueError("Insulation thickness too small compared to minimum required thickness.")
            S_c = np.pi * R**2 + 2 * np.pi * R * H
            Q_sb = (T_sto_last - self.T_soil) * K_sb * S_c
            return Q_sb / 1000  # Convert to kW

        elif self.storage_type == "truncated_cone" or self.storage_type == "truncated_trapezoid":
            # Loss from sides
            H = self.dimensions[2]
            a = self.ds_side / self.lambda_side + np.pi * H / (2 * self.lambda_soil)
            b = np.pi / self.lambda_soil
            K_s = (1 / (b * H)) * np.log((a + b * H) / a)
            Q_s = (T_sto_last - self.T_soil) * K_s * self.S_side

            # Loss from bottom
            c = self.db_bottom / self.lambda_bottom + np.pi * H / (2 * self.lambda_soil)
            K_b = (1 / (2 * b * self.dimensions[1])) * np.log((c + b * self.dimensions[1]) / c)
            Q_b = (T_sto_last - self.T_soil) * K_b * self.S_bottom
            return (Q_s + Q_b) / 1000  # Convert to kW

    def simulate(self, Q_in, Q_out):
        for t in range(0, self.hours):
            # Calculate heat loss based on the last temperature
            self.Q_loss[t] = self.calculate_heat_loss(self.T_sto[t-1])

            if t == 0:
                # Convert initial stored heat calculation to kWh (1 kWh = 3.6e6 J)
                self.Q_sto[t] = self.volume * self.rho * self.cp * (self.T_sto[t] - self.T_ref) / 3.6e6  # Initial stored heat in kWh

            else:
                # Energy balance: Use kWh (3600 seconds in 1 hour)
                self.Q_sto[t] = self.Q_sto[t-1] + (Q_in[t] - Q_out[t] - self.Q_loss[t])  # Stored heat in kWh (input/output in kW)

                # Update storage temperature based on kWh stored
                self.T_sto[t] = (self.Q_sto[t] * 3.6e6) / (self.volume * self.rho * self.cp) + self.T_ref  # Convert back to temperature in °C

            # Limit temperature within max and min bounds
            if self.T_sto[t] > self.T_max:
                self.T_sto[t] = self.T_max
            elif self.T_sto[t] < self.T_min:
                self.T_sto[t] = self.T_min
    
    def calculate_stratified_heat_loss(self, T_sto_layers):
        """
        Calculate heat loss for each layer in a stratified storage system based on geometry.
        """
        self.Q_loss_layers = np.zeros(len(T_sto_layers))  # Wärmeverlust in kW für jede Schicht

        for i, T_layer in enumerate(T_sto_layers):
            if self.storage_type == "cylindrical_overground":
                # Verluste für einen zylindrischen überirdischen Speicher
                if i == 0:  # Obere Schicht
                    Q_loss_top = (self.lambda_top / self.dt_top) * self.S_top * (T_layer - self.T_amb) / 1000
                    self.Q_loss_layers[i] = Q_loss_top
                elif i == len(T_sto_layers) - 1:  # Untere Schicht
                    Q_loss_bottom = (self.db_bottom / self.lambda_bottom + 4 * self.dimensions[0] / (3 * np.pi * self.lambda_soil))**(-1) * self.S_bottom * (T_layer - self.T_amb) / 1000
                    self.Q_loss_layers[i] = Q_loss_bottom
                else:  # Seitenschichten
                    Q_loss_side = (self.lambda_side / self.ds_side) * (T_layer - self.T_amb) * self.S_side / len(T_sto_layers) / 1000
                    self.Q_loss_layers[i] = Q_loss_side

            elif self.storage_type == "cylindrical_underground":
                # Verluste für einen unterirdischen zylindrischen Speicher
                R = self.dimensions[0]
                H = self.dimensions[1]
                d_min = (self.lambda_side / self.lambda_soil) * R * 0.37
                if self.ds_side > 2 * d_min:
                    K_sb = (self.ds_side / self.lambda_side + 0.52 * R / self.lambda_soil)**(-1)
                else:
                    raise ValueError("Insulation thickness too small compared to minimum required thickness.")
                S_c = np.pi * R**2 + 2 * np.pi * R * H

                if i == 0:  # Obere Schicht
                    Q_loss_top = (self.lambda_top / self.dt_top) * self.S_top * (T_layer - self.T_amb) / 1000
                    self.Q_loss_layers[i] = Q_loss_top
                else:  # Seitenschichten und Boden
                    Q_loss_sb = K_sb * S_c * (T_layer - self.T_soil) / len(T_sto_layers) / 1000
                    self.Q_loss_layers[i] = Q_loss_sb

            elif self.storage_type == "truncated_cone" or self.storage_type == "truncated_trapezoid":
                # Verluste für PTES-Speicher (konisch und trapezförmig)
                H = self.dimensions[2]
                a = self.ds_side / self.lambda_side + np.pi * H / (2 * self.lambda_soil)
                b = np.pi / self.lambda_soil
                K_s = (1 / (b * H)) * np.log((a + b * H) / a)

                c = self.db_bottom / self.lambda_bottom + np.pi * H / (2 * self.lambda_soil)
                K_b = (1 / (2 * b * self.dimensions[1])) * np.log((c + b * self.dimensions[1]) / c)

                if i == 0:  # Obere Schicht
                    Q_loss_top = (self.lambda_top / self.dt_top) * self.S_top * (T_layer - self.T_amb) / 1000
                    self.Q_loss_layers[i] = Q_loss_top
                elif i == len(T_sto_layers) - 1:  # Untere Schicht
                    Q_loss_bottom = K_b * self.S_bottom * (T_layer - self.T_soil) / 1000
                    self.Q_loss_layers[i] = Q_loss_bottom
                else:  # Seitenschichten
                    Q_loss_side = K_s * self.S_side * (T_layer - self.T_soil) / len(T_sto_layers) / 1000
                    self.Q_loss_layers[i] = Q_loss_side

        return np.sum(self.Q_loss_layers)  # Gesamtverlust in kW

    def simulate_stratified(self, Q_in, Q_out, num_layers=5, thermal_conductivity=0.6):
        """
        Q_in: Eingangsleistung in kW
        Q_out: Ausgangsleistung in kW
        thermal_conductivity: Wärmeleitfähigkeit des Mediums (in W/m*K, z.B. für Wasser 0.6)
        """
        # Berechne die Dicke der Schichten basierend auf der Speicherdimension
        if self.storage_type == "cylindrical":
            height = self.dimensions[1]  # Höhe des zylindrischen Speichers
            layer_thickness = height / num_layers
        elif self.storage_type == "truncated_cone":
            height = self.dimensions[2]  # Höhe des rechteckigen Speichers
            layer_thickness = height / num_layers
        elif self.storage_type == "truncated_trapezoid":
            height = self.dimensions[2]  # Höhe des Pit-Speichers
            layer_thickness = height / num_layers
        else:
            raise ValueError("Unsupported storage type for layer thickness calculation")

        layer_volume = self.volume / num_layers  # Volumen pro Schicht
        self.T_sto_layers = np.full((self.hours, num_layers), self.T_sto[0])  # Initialisiere Schichttemperaturen
        heat_stored_per_layer = np.zeros(num_layers)  # Wärme in jeder Schicht

        for t in range(0, self.hours):
            # Berechne den stratified Wärmeverlust und speichere ihn
            self.Q_loss[t] = self.calculate_stratified_heat_loss(self.T_sto_layers[t-1])
            
            # Berechne die verfügbare Wärme im Zeitschritt (Bilanz Input - Output)
            remaining_heat = Q_in[t] - Q_out[t]  # Verfügbare Wärme, nach Abzug des Outputs
            
            if t == 0:
                # Initiale gespeicherte Wärme in kWh (1 kWh = 3.6e6 J)
                self.Q_sto[t] = self.volume * self.rho * self.cp * (self.T_sto[t] - self.T_ref) / 3.6e6
                heat_stored_per_layer[:] = self.Q_sto[t] / num_layers  # Anfangsgleichverteilung der Wärme
            else:
                # **Entlade Schichten, wenn remaining_heat negativ ist (Wärmebedarf höher als Input)**
                for i in range(num_layers):  # Entlade von unten nach oben
                    if remaining_heat < 0:
                        # Wärmebedarf ist höher als die Eingangsleistung, Speicher entlädt
                        available_heat_in_layer = (self.T_sto_layers[t-1, i] - self.T_min) * layer_volume * self.rho * self.cp / 3.6e6  # verfügbare Wärme in kWh
                        heat_needed = abs(remaining_heat)

                        if heat_needed >= available_heat_in_layer:
                            # Schicht wird komplett entladen
                            heat_stored_per_layer[i] -= available_heat_in_layer
                            self.T_sto_layers[t, i] = self.T_min  # Temperatur erreicht die minimale Grenze
                            remaining_heat += available_heat_in_layer  # Entlade die verfügbare Wärme
                        else:
                            # Schicht wird nur teilweise entladen
                            heat_stored_per_layer[i] -= heat_needed
                            self.T_sto_layers[t, i] = self.T_sto_layers[t-1, i] - (heat_needed * 3.6e6) / (layer_volume * self.rho * self.cp)
                            remaining_heat = 0  # Wärmebedarf gedeckt, keine weitere Entladung erforderlich

                # **Lade Schichten, wenn remaining_heat positiv ist (Input höher als Wärmebedarf)**
                for i in range(num_layers):  # Belade von oben nach unten
                    heat_loss_layer = self.Q_loss_layers[i]  # Wärmeverlust für die aktuelle Schicht

                    # Berechne die maximal mögliche Wärme, um die Schicht auf T_max zu bringen
                    max_heat_in_layer = (self.T_max - self.T_sto_layers[t-1, i]) * layer_volume * self.rho * self.cp / 3.6e6  # in kWh

                    if remaining_heat > 0:
                        if remaining_heat >= max_heat_in_layer:
                            # Schicht wird komplett aufgeheizt
                            heat_stored_per_layer[i] += max_heat_in_layer
                            self.T_sto_layers[t, i] = self.T_max  # Maximaltemperatur erreicht
                            remaining_heat -= max_heat_in_layer  # Restwärme geht in die nächste Schicht
                        else:
                            # Schicht wird nur teilweise aufgeheizt
                            heat_stored_per_layer[i] += remaining_heat
                            self.T_sto_layers[t, i] = self.T_sto_layers[t-1, i] + (remaining_heat * 3.6e6) / (layer_volume * self.rho * self.cp)
                            remaining_heat = 0  # Keine Restwärme mehr
                    else:
                        # Falls keine Restwärme vorhanden ist, bleibt die Temperatur konstant
                        self.T_sto_layers[t, i] = self.T_sto_layers[t-1, i]

                    # Ziehe Wärmeverluste von der gespeicherten Wärme in der Schicht ab
                    heat_stored_per_layer[i] -= heat_loss_layer / 3600  # Wärmeverlust in kWh

                    # Begrenze die Temperatur, falls sie unter die Minimaltemperatur fällt
                    if self.T_sto_layers[t, i] < self.T_min:
                        self.T_sto_layers[t, i] = self.T_min

                # Berechne den Wärmetransport zwischen benachbarten Schichten
                for i in range(num_layers - 1):
                    # Berechnung des Wärmeflusses zwischen Schicht i und i+1
                    delta_T = self.T_sto_layers[t, i] - self.T_sto_layers[t, i + 1]
                    heat_transfer = thermal_conductivity * self.S_side * delta_T / layer_thickness  # W = J/s
                    
                    # Umrechnung in kWh für den Zeitintervall (1 Stunde = 3600 Sekunden)
                    heat_transfer_kWh = heat_transfer / 3.6e6 * 3600  # kWh pro Stunde
                    
                    # Wärme von der oberen Schicht (i) abziehen und in die untere Schicht (i+1) hinzufügen
                    heat_stored_per_layer[i] -= heat_transfer_kWh
                    heat_stored_per_layer[i + 1] += heat_transfer_kWh

                    # Aktualisiere die Temperaturen basierend auf dem neuen Wärmeinhalt
                    self.T_sto_layers[t, i] = (heat_stored_per_layer[i] * 3.6e6) / (layer_volume * self.rho * self.cp) + self.T_ref
                    self.T_sto_layers[t, i + 1] = (heat_stored_per_layer[i + 1] * 3.6e6) / (layer_volume * self.rho * self.cp) + self.T_ref

            # Berechne die Gesamtwärme im Speicher
            self.Q_sto[t] = np.sum(heat_stored_per_layer)  # Gespeicherte Wärme in kWh

            # Aktualisiere die Hauptspeichertemperatur als Durchschnittstemperatur der Schichten
            self.T_sto[t] = np.average(self.T_sto_layers[t])

    def calculate_operational_costs(self, energy_price_per_kWh):
        # Convert J to kWh (1 kWh = 3.6e6 J)
        total_energy_loss_kWh = np.sum(self.Q_loss) # Total energy loss in kWh
        self.operational_costs = total_energy_loss_kWh * energy_price_per_kWh

    def calculate_efficiency(self, Q_in, Q_out):
        total_input_energy = np.sum(Q_in) # Total input energy in kWh
        total_output_energy = np.sum(Q_out) # Total output energy in kWh
        change_in_stored_energy = self.Q_sto[-1] - self.Q_sto[0] # Change in stored energy in kWh
        self.efficiency = total_output_energy / total_input_energy # Efficiency as a ratio

    def optimize_storage_geometry(self, Q_in, Q_out):
        def objective_function(dimensions):
            self.dimensions = dimensions
            self.volume, self.S_top, self.S_side, self.S_bottom = self.calculate_cylindrical_geometry(dimensions)
            T_sto = self.simulate(Q_in, Q_out)
            Q_loss = np.sum([self.calculate_heat_loss(T) for T in T_sto])
            return Q_loss  # Minimize heat loss
        
        initial_guess = (10, 12)  # Initial guess for radius and height
        result = minimize(objective_function, initial_guess, method='Nelder-Mead')
        optimal_dimensions = result.x
        return optimal_dimensions
    
    def plot_3d_temperature_distribution(self, ax, time_step):
        """3D plot to visualize the temperature stratification in the storage as filled layers (cylinder or rectangular)."""
        if self.storage_type == "cylindrical":
            radius, height = self.dimensions
            
            # Zylinder-Koordinaten für die Schichtunterteilungen
            z_layers = np.linspace(0, height, self.T_sto_layers.shape[1] + 1)  # Höhenkoordinaten für die Schichtenübergänge
            theta = np.linspace(0, 2 * np.pi, 50)  # Winkelkoordinaten für den Zylinder
            theta_grid, z_grid = np.meshgrid(theta, z_layers)
            x_grid = radius * np.cos(theta_grid)
            y_grid = radius * np.sin(theta_grid)

            # Umkehren der Z-Koordinaten und Temperaturwerte, sodass heiß oben ist
            z_layers = np.flip(z_layers)  # Z-Koordinaten umkehren
            T_layers_reversed = np.flip(self.T_sto_layers[time_step])  # Temperatur-Schichten umkehren

            # Plot each layer as a filled cylinder between two z-levels
            for i in range(self.T_sto_layers.shape[1]):
                color_value = (self.T_sto_layers[time_step, i] - self.T_min) / (self.T_max - self.T_min)
                color = plt.cm.coolwarm(color_value)  # Color gradient based on temperature
                color_value_reversed = (T_layers_reversed[i] - self.T_min) / (self.T_max - self.T_min)
                color_reversed = plt.cm.coolwarm(color_value_reversed)  # Farbverlauf basierend auf der Temperatur

                # Erstelle eine 2D-Matrix für die facecolors basierend auf der Temperatur
                facecolors = np.tile(color_reversed[:3], (x_grid.shape[0], x_grid.shape[1], 1))

                # Zylinderoberfläche plotten
                ax.plot_surface(x_grid, y_grid, z_grid[i] * np.ones_like(x_grid), facecolors=facecolors, rstride=1, cstride=1, alpha=0.7)
                ax.plot_surface(x_grid, y_grid, z_grid[i+1] * np.ones_like(x_grid), facecolors=facecolors, rstride=1, cstride=1, alpha=0.7)

                # Plot der vertikalen Seitenflächen zwischen zwei Z-Koordinaten
                for j in range(x_grid.shape[1] - 1):
                    ax.plot([x_grid[0, j], x_grid[0, j + 1]], [y_grid[0, j], y_grid[0, j + 1]], [z_layers[i], z_layers[i]], color=color[:3], alpha=0.7)
                    ax.plot([x_grid[-1, j], x_grid[-1, j + 1]], [y_grid[-1, j], y_grid[-1, j + 1]], [z_layers[i + 1], z_layers[i + 1]], color=color[:3], alpha=0.7)
                    
                    # Schließt die vertikalen Seitenflächen ab
                    ax.plot([x_grid[0, j], x_grid[0, j]], [y_grid[0, j], y_grid[0, j]], [z_layers[i], z_layers[i + 1]], color=color[:3], alpha=0.7)
                    ax.plot([x_grid[-1, j], x_grid[-1, j]], [y_grid[-1, j], y_grid[-1, j]], [z_layers[i], z_layers[i + 1]], color=color[:3], alpha=0.7)

        if self.storage_type == "truncated_cone":
            """3D plot to visualize the temperature stratification in a truncated cone PTES."""
            top_radius, bottom_radius, height = self.dimensions
            z_layers = np.linspace(0, height, self.T_sto_layers.shape[1] + 1)
            
            # Zylinder-Koordinaten für die Schichtunterteilungen
            theta = np.linspace(0, 2 * np.pi, 50)  # Winkelkoordinaten für den Zylinder
            
            # Calculate the radius for each z-layer based on the linear slope
            radii = np.linspace(bottom_radius, top_radius, len(z_layers))
            
            for i in range(self.T_sto_layers.shape[1]):
                # Matching dimensions for x_grid, y_grid, and z_grid
                theta_grid, z_grid = np.meshgrid(theta, z_layers[i:i+2])
                x_grid = np.outer(np.cos(theta), radii[i:i+2])
                y_grid = np.outer(np.sin(theta), radii[i:i+2])

                color_value_reversed = (np.flip(self.T_sto_layers[time_step])[i] - self.T_min) / (self.T_max - self.T_min)
                color_reversed = plt.cm.coolwarm(color_value_reversed)

                facecolors = np.tile(color_reversed[:3], (x_grid.shape[0], x_grid.shape[1], 1))

                # Plot the surface with correctly shaped arrays
                ax.plot_surface(x_grid, y_grid, np.transpose(z_grid), facecolors=facecolors, rstride=1, cstride=1, alpha=0.7)


        if self.storage_type == "truncated_trapezoid":
            """3D plot to visualize the temperature stratification in a truncated trapezoid PTES."""
            # Swap top and bottom dimensions to ensure the narrow end is at the bottom
            bottom_length, bottom_width, top_length, top_width, height = self.dimensions

            z_layers = np.linspace(0, height, self.T_sto_layers.shape[1] + 1)

            # Calculate length and width at each z-layer based on linear slope
            lengths = np.linspace(bottom_length, top_length, len(z_layers))
            widths = np.linspace(bottom_width, top_width, len(z_layers))

            for i in range(self.T_sto_layers.shape[1]):
                # Bottom and top layer coordinates
                r_bottom = [-lengths[i] / 2, lengths[i] / 2]
                s_bottom = [-widths[i] / 2, widths[i] / 2]
                r_top = [-lengths[i+1] / 2, lengths[i+1] / 2]
                s_top = [-widths[i+1] / 2, widths[i+1] / 2]
                t_bottom = z_layers[i]
                t_top = z_layers[i + 1]

                color_value_reversed = (np.flip(self.T_sto_layers[time_step])[i] - self.T_min) / (self.T_max - self.T_min)
                color_reversed = plt.cm.coolwarm(color_value_reversed)

                # Create a 2D array for the facecolors
                facecolors = np.tile(color_reversed[:3], (2, 4, 1))

                # Plot bottom and top surfaces
                ax.plot_surface(np.array([[r_bottom[0], r_bottom[0], r_bottom[1], r_bottom[1]],
                                        [r_top[0], r_top[0], r_top[1], r_top[1]]]),
                                np.array([[s_bottom[0], s_bottom[1], s_bottom[1], s_bottom[0]],
                                        [s_top[0], s_top[1], s_top[1], s_top[0]]]),
                                np.array([[t_bottom, t_bottom, t_bottom, t_bottom],
                                        [t_top, t_top, t_top, t_top]]),
                                facecolors=facecolors, rstride=1, cstride=1, alpha=0.7)

                # Plot side faces (ensuring all walls are plotted)
                ax.plot_surface(np.array([[r_bottom[0], r_top[0]], [r_bottom[1], r_top[1]]]),
                                np.array([[s_bottom[0], s_top[0]], [s_bottom[0], s_top[0]]]),
                                np.array([[t_bottom, t_top], [t_bottom, t_top]]),
                                facecolors=np.tile(color_reversed[:3], (2, 2, 1)), alpha=0.7)

                ax.plot_surface(np.array([[r_bottom[0], r_top[0]], [r_bottom[1], r_top[1]]]),
                                np.array([[s_bottom[1], s_top[1]], [s_bottom[1], s_top[1]]]),
                                np.array([[t_bottom, t_top], [t_bottom, t_top]]),
                                facecolors=np.tile(color_reversed[:3], (2, 2, 1)), alpha=0.7)

                ax.plot_surface(np.array([[r_bottom[0], r_bottom[0]], [r_top[0], r_top[0]]]),
                                np.array([[s_bottom[0], s_top[0]], [s_bottom[1], s_top[1]]]),
                                np.array([[t_bottom, t_top], [t_bottom, t_top]]),
                                facecolors=np.tile(color_reversed[:3], (2, 2, 1)), alpha=0.7)

                # Ensure bottom closure
                ax.plot_surface(np.array([[r_bottom[0], r_bottom[1]]]),
                                np.array([[s_bottom[0], s_bottom[1]]]),
                                np.array([[t_bottom, t_bottom]]),
                                color=color_reversed[:3], alpha=0.7)
        else:
            raise ValueError("Unsupported storage type for 3D plot")

        # Add labels, title, and color bar only if they haven't been added before
        if not self.labels_exist:
            ax.set_title('Temperature Stratification (Time Step {})'.format(time_step))
            ax.set_xlabel('X (m)')
            ax.set_ylabel('Y (m)')
            ax.set_zlabel('Height (m)')
            ax.set_box_aspect([1, 1, 2])  # Verhältnis von X, Y, Z anpassen
            self.labels_exist = True  # Set flag to prevent re-drawing

        if not self.colorbar_exists:
            # Hinzufügen einer Farbskala zur Veranschaulichung der Temperatur
            mappable = plt.cm.ScalarMappable(cmap=plt.cm.coolwarm)
            mappable.set_array([self.T_min, self.T_max])
            cbar = plt.colorbar(mappable, ax=ax, shrink=0.5, aspect=5)
            cbar.set_label('Temperature (°C)')
            self.colorbar_exists = True  # Set flag to prevent re-drawing
    
    def plot_results(self, Q_in, Q_out):
            fig = plt.figure(figsize=(16, 10))
            axs1 = fig.add_subplot(2, 3, 1)
            axs2 = fig.add_subplot(2, 3, 2)
            axs3 = fig.add_subplot(2, 3, 3)
            axs4 = fig.add_subplot(2, 3, 4)
            axs5 = fig.add_subplot(2, 3, 5)
            axs6 = fig.add_subplot(2, 3, 6, projection='3d')

            # Q_in and Q_out
            axs1.plot(Q_in, label='Heat Input', color='red')
            axs1.plot(Q_out, label='Heat Output', color='blue')
            axs1.set_ylabel('Heat (kW)')
            axs1.set_title('Heat Input and Output over Time')
            axs1.legend()

            # Plot storage temperature
            axs2.plot(self.T_sto, label='Storage Temperature')
            axs2.set_ylabel('Temperature (°C)')
            axs2.set_title(f'Storage Temperature over Time ({self.storage_type.capitalize()} Storage)')
            axs2.legend()

            # Plot heat loss
            axs3.plot(self.Q_loss, label='Heat Loss', color='orange')
            axs3.set_ylabel('Heat Loss (kW)')
            axs3.set_title('Heat Loss over Time')
            axs3.legend()

            # Plot stored heat
            axs4.plot(self.Q_sto, label='Stored Heat', color='green')
            axs4.set_ylabel('Stored Heat (kWh)')
            axs4.set_title('Stored Heat over Time')
            axs4.legend()

            # Plot stratified storage temperatures
            for i in range(self.T_sto_layers.shape[1]):
                axs5.plot(self.T_sto_layers[:, i], label=f'Layer {i+1}')
            axs5.set_xlabel('Time (hours)')
            axs5.set_ylabel('Temperature (°C)')
            axs5.set_title('Stratified Storage Temperatures')
            axs5.legend()

            # Plot 3D geometry
            self.plot_3d_temperature_distribution(axs6, 3000)

            plt.tight_layout()
            plt.show()

if __name__ == '__main__':
    # Complete the example usage for cylindrical storage
    params = {
        #"storage_type": "cylindrical",  # Choose between "cylindrical", "truncated_cone", "truncated_trapezoid"
        #"storage_type": "truncated_cone",
        "storage_type": "truncated_trapezoid",
        #"dimensions": (25, 25),  # Radius (m), Height (m) for cylindrical
        #"dimensions": (10, 5, 25),  # Top radius, Bottom radius, Height for truncated cone
        "dimensions": (20, 20, 50, 50, 15),  # Top length, Top width, Bottom length, Bottom width, Height for truncated trapezoid
        "rho": 1000,  # kg/m³ (density of water)
        "cp": 4180,  # J/kg*K (specific heat capacity of water)
        "T_ref": 10,  # °C reference temperature

        "lambda_top": 0.04,  # W/m*K for top insulation
        "lambda_side": 0.03,  # W/m*K for side insulation
        "lambda_bottom": 0.05,  # W/m*K for bottom insulation
        "lambda_soil": 1.5,  # W/m*K for soil thermal conductivity
        "dt_top": 0.3,  # m thickness of top insulation
        "ds_side": 0.4,  # m thickness of side insulation
        "db_bottom": 0.5,  # m thickness of bottom insulation

        "T_amb": 10,  # °C ambient temperature
        "T_soil": 10,  # °C soil temperature
        "T_max": 95,  # °C maximum storage temperature
        "T_min": 40,  # °C minimum storage temperature
        "initial_temp": 60,  # Initial storage temperature
        "hours": 8760,  # Number of hours in a year
        "num_layers": 5,  # Number of layers for stratified storage
        "thermal_conductivity": 0.6  # W/m*K thermal conductivity of the medium, here water
    }
    # Create instance of the class for cylindrical storage
    STES = ThermalStorage(**params)

    # Simulated heat input and output (example random values)
    Q_in = np.random.uniform(450, 455, params['hours'])  # Heat input in kW
    #Q_out = np.random.uniform(100, 200, params['hours'])  # Heat output in kW

    # Load Q_out from Lastgang.csv
    file_path = os.path.abspath('currently_not_used\STES\Lastgang.csv')
    df = pd.read_csv(file_path, delimiter=';', encoding='utf-8')
    Q_out = df['Gesamtwärmebedarf_Gebäude_kW'].values # Heat output kW

    # Run simulation
    STES.simulate_stratified(Q_in, Q_out)
    STES.calculate_efficiency(Q_in, Q_out)
    energy_price_per_kWh = 0.10  # €/kWh
    STES.calculate_operational_costs(energy_price_per_kWh)

    # calculate operational costs
    print(f"Operational costs: {(STES.operational_costs):.2f} €")

    # Calculate efficiency
    print(f"Storage efficiency: {STES.efficiency * 100:.2f}%")

    # Plot the results
    STES.plot_results(Q_in, Q_out)

    # Interactive 3D plot
    interactive_plot(STES)

    # Optimize storage geometry
    #print(f"Optimal dimensions: {STES.optimize_storage_geometry(Q_in, Q_out)}")