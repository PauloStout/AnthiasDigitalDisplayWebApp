# app/routes.py
from flask import request, jsonify, render_template, redirect, url_for
from app import app
import main
import os

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/create_asset_page')
def create_asset_page():
    devices = main.read_apis_from_csv(main.get_csv_path())  # Get devices from CSV
    return render_template("create_asset.html", devices=devices)


@app.route('/view_assets')
def view_assets():
    csv_file = main.get_csv_path()
    devices = main.read_apis_from_csv(csv_file)

    all_assets = {}
    for device in devices:
        ip = device["ip"]
        label = device.get("label", ip)  # fallback to IP if no label
        assets = main.get_assets_from_device(ip)

        if isinstance(assets, dict) and assets.get("error"):
            all_assets[ip] = {"label": label, "error": assets["error"]}
        else:
            all_assets[ip] = {"label": label, "assets": assets}

    return render_template("view_assets.html", assets=all_assets)

@app.route('/create_asset', methods=['POST'])
def create_asset():
    name = request.form.get('name')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    duration_str = request.form.get('duration', '0').strip()

    selected_ips = request.form.getlist("selected_ips")  # Get selected IPs

    if not selected_ips:
        return jsonify({"error": "No devices selected. Please choose at least one device."}), 400

    try:
        duration = int(duration_str) if duration_str else 0
    except ValueError:
        return jsonify({"error": "Duration must be an integer."}), 400

    if not all([name, start_date, end_date]):
        return jsonify({"error": "Missing required asset metadata."}), 400

    metadata = {
        "name": name,
        "start_date": start_date,
        "end_date": end_date,
        "duration": duration
    }

    if 'file' in request.files and request.files['file'].filename != "":
        file_obj = request.files['file']
        results = main.create_file_asset_on_selected_devices(file_obj, metadata, selected_ips)
    elif request.form.get('asset_url', '').strip() != "":
        asset_url = request.form.get('asset_url').strip()
        metadata["asset_url"] = asset_url
        results = main.create_url_asset_on_selected_devices(metadata, selected_ips)
    else:
        return jsonify({"error": "No asset provided. Please upload a file or enter an asset URL."}), 400

    return jsonify(results)


# New route to render deletion form submission from view_assets page
@app.route('/delete_assets', methods=['POST'])
def delete_assets():
    # Expect a list of deletion strings "ip|asset_id" from form field "selected_assets"
    selected = request.form.getlist("selected_assets")
    if not selected:
        return redirect(url_for("view_assets"))
    deletion_results = main.delete_selected_assets(selected)
    # For simplicity, redirect back to view_assets (or you can render a page showing deletion_results)
    return redirect(url_for("view_assets"))

@app.route('/set_assets_active', methods=['POST'])
def set_assets_active():
    # Expect a list of strings "ip|asset_id" from form field "selected_assets"
    selected = request.form.getlist("selected_assets")
    if not selected:
        return redirect(url_for("view_assets"))

    results = main.set_selected_assets_enabled(selected, True)
    # you can log results or flash them; we'll just redirect back to view
    return redirect(url_for("view_assets"))


@app.route('/set_assets_inactive', methods=['POST'])
def set_assets_inactive():
    selected = request.form.getlist("selected_assets")
    if not selected:
        return redirect(url_for("view_assets"))

    results = main.set_selected_assets_enabled(selected, False)
    return redirect(url_for("view_assets"))

@app.route('/anthias_status')
def anthias_status():
    # Get the results from main()
    results = main.main()
    return render_template("anthias_status.html", results=results)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=3500)
