README – Dematic Pallet Tracking System
1. What this project is

This project is a small Flask web app that reads a warehouse log file and shows how pallets move through the system. It was created for SPAT Assessment 2. The goal is to take the raw log events and turn them into a visual layout that is easier to understand.

2. What the system does

Reads the log file and extracts pallet movements

Tracks where each pallet is and where it is going next

Shows a visual layout of the warehouse

Highlights each point the pallet visits in order

Lets us search for a pallet ID

Shows pallet history (all events for that pallet)

Displays faults if they appear in the logs

Shows a live event stream and all pallets currently in the system

3. How to run the system

Install flask - pip install flask

Make sure the log file is in the project folder and named - final_logs.txt.txt

Run the app - python app.py

Open the system in your browser - http://127.0.0.1:5000

4. How it works

Backend (Python/Flask):
Reads each line of the log and updates pallet locations, status, and history.

Frontend (HTML/CSS):
Shows the warehouse diagram and highlights the pallet path.
Also displays the event table, faults, pallet summary and history.

The page refreshes every few seconds so new log entries appear automatically.

5. Features completed

Full warehouse layout diagram

Pallet movement animation

Live updating from the log

Pallet search

Pallet history view

Fault detection

Current pallet tracking

Event stream + pallet summary table

6. How to test it

Search test - enter a pallet ID and check the details update.

Movement test - the diagram should highlight each node the pallet visits.

Fault test - add a FAULT line to the log and it should appear in the faults panel.

Live update test - add a new line to the log file and check it appears in the event stream.

7. Group contributions

Name	     Contribution
Member 1 - Log reading and extraction
Member 2 - State tracking logic
Member 3 - System layout diagram
Member 4 - Animation and highlighting
Member 5 - Fault + history panel
Member 6 - Testing and debugging
All members -	Documentation (including report + README)

9. Summary

This system reads a Dematic-style log file and visually shows how pallets move through the warehouse.
It includes searching, history, fault detection, and a live event feed.
All main requirements of the assessment have been completed.




