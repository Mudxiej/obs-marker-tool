-- OBS Marker Server Auto-Lifecycle & Properties Script
local obs = obslua

local hotkey_id = obs.OBS_INVALID_HOTKEY_ID
local custom_output_dir = ""
local folder_naming = "timestamp"
local export_txt = true
local export_csv = true
local export_xml = true
local export_fcpxml = true
local export_json = true

function script_description()
    return "OBS Marker Tool Service\n\n" ..
           "• Save Folder: Default saves alongside your OBS recordings (next to video files). Use the property below to set a custom folder.\n" ..
           "• Global Hotkey: Go to OBS Settings -> Hotkeys and search for 'Marker Tool: Freeze Timestamp'. Bind F8 or any key combination!\n" ..
           "• Server Lifecycle: Automatically started when OBS launches, safely terminated when OBS exits."
end

local function get_script_dir()
    local p = script_path()
    -- script_path() may return a directory or a full file path depending on OBS version.
    -- Normalize separators, strip a trailing filename, ensure trailing backslash.
    p = string.gsub(p, "/", "\\")
    if string.lower(string.sub(p, -4)) == ".lua" then
        local dir = string.match(p, "^(.*\\)[^\\]*$")
        if dir then
            p = dir
        end
    end
    if string.sub(p, -1) ~= "\\" then
        p = p .. "\\"
    end
    return p
end

local function read_config_value(key, fallback)
    local win_dir = get_script_dir()
    local f = io.open(win_dir .. "config.json", "r")
    if not f then return fallback end
    local content = f:read("*a")
    f:close()
    if not content then return fallback end
    local s = string.match(content, '"' .. key .. '"%s*:%s*"([^"]-)"')
    if s ~= nil then return s end
    local b = string.match(content, '"' .. key .. '"%s*:%s*(%a+)')
    if b == "true" then return true elseif b == "false" then return false end
    local n = string.match(content, '"' .. key .. '"%s*:%s*(-?[%d%.]+)')
    if n ~= nil then return n end
    return fallback
end

local function write_config()
    local win_dir = get_script_dir()
    local config_file = win_dir .. "config.json"
    -- Merge-safe: preserve fps keys written by the server so Lua saves
    -- don't clobber them (and vice versa).
    local fps_num = read_config_value("fps_num", "60")
    local fps_den = read_config_value("fps_den", "1")
    local function boolstr(v) if v then return "true" else return "false" end end
    local f = io.open(config_file, "w")
    if f then
        local safe_dir = string.gsub(custom_output_dir or "", "\\", "\\\\")
        f:write('{"custom_output_dir": "' .. safe_dir .. '", "folder_naming": "' .. (folder_naming or "timestamp") .. '", "fps_num": ' .. tostring(fps_num) .. ', "fps_den": ' .. tostring(fps_den)
            .. ', "export_txt": ' .. boolstr(export_txt) .. ', "export_csv": ' .. boolstr(export_csv) .. ', "export_xml": ' .. boolstr(export_xml) .. ', "export_fcpxml": ' .. boolstr(export_fcpxml) .. ', "export_json": ' .. boolstr(export_json) .. '}')
        f:close()
    end
end

local function trigger_freeze(pressed)
    if not pressed then return end
    local win_dir = get_script_dir()
    local flag_file = win_dir .. "freeze_trigger.flag"
    local f = io.open(flag_file, "w")
    if f then
        f:write(tostring(os.time()))
        f:close()
    end
end

local function read_saved_port()
    local win_dir = get_script_dir()
    local f = io.open(win_dir .. "port.txt", "r")
    if not f then return nil end
    local content = f:read("*l") or ""
    f:close()
    local port = tonumber((string.gsub(content or "", "%s+", "")))
    if port and port >= 1 and port <= 65535 then
        return math.floor(port)
    end
    return nil
end

local function probe_port(port)
    local res = os.execute('curl.exe -s --fail --connect-timeout 1 http://127.0.0.1:' .. tostring(port) .. '/api/status > NUL 2>&1')
    return res == 0 or res == true
end

local function find_active_port()
    local saved = read_saved_port()
    if saved and probe_port(saved) then
        return saved
    end
    for port = 8765, 8770 do
        if probe_port(port) then
            return port
        end
    end
    return nil
end

local function on_open_folder(props, prop)
    if custom_output_dir ~= nil and custom_output_dir ~= "" then
        -- Escape embedded quotes to avoid command injection via crafted path
        local safe = string.gsub(custom_output_dir, '"', '')
        os.execute('start "" explorer.exe "' .. safe .. '"')
    else
        local port = find_active_port() or 8765
        os.execute('start "" curl.exe -s --connect-timeout 2 http://127.0.0.1:' .. tostring(port) .. '/api/open_folder')
    end
    return true
end

function script_properties()
    local props = obs.obs_properties_create()

    -- 1. Output directory property
    obs.obs_properties_add_path(props, "custom_output_dir", "Save Location (Leave blank for OBS Recording folder)", obs.OBS_PATH_DIRECTORY, "", "")

    -- 2. Folder naming: timestamp folders always, or rename to the video
    -- filename on stop (outputPath arrives on STOPPED; active sessions stay
    -- in timestamp folders so a crash never loses markers).
    local naming = obs.obs_properties_add_list(props, "folder_naming", "Folder Naming", obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    obs.obs_property_list_add_string(naming, "Timestamp (Markers_YYYY-MM-DD_HH-MM-SS)", "timestamp")
    obs.obs_property_list_add_string(naming, "Video filename (rename on stop)", "video")

    -- 3. Export format toggles (all on = today's 5-file behavior)
    obs.obs_properties_add_bool(props, "export_txt", "Export YouTube Chapters (markers.txt)")
    obs.obs_properties_add_bool(props, "export_csv", "Export CSV Timeline (markers.csv)")
    obs.obs_properties_add_bool(props, "export_xml", "Export Premiere Pro XML (premiere_sequence.xml)")
    obs.obs_properties_add_bool(props, "export_fcpxml", "Export Final Cut Pro XML (final_cut_pro.fcpxml)")
    obs.obs_properties_add_bool(props, "export_json", "Export JSON Timeline (markers.json)")

    -- 4. Open folder button
    obs.obs_properties_add_button(props, "btn_open", "Open Save Folder in Explorer", on_open_folder)

    return props
end

local function read_bool_setting(settings, key, current)
    -- Old profiles predate these keys: without a user value, keep today's
    -- all-on behavior instead of OBS's C-default false.
    local has_fn = obs.obs_data_has_user_value
    if has_fn then
        local ok_has, has_user = pcall(has_fn, settings, key)
        if ok_has and has_user == false then
            return current
        end
    end
    local ok, val = pcall(obs.obs_data_get_bool, settings, key)
    if not ok then return current end
    return val
end

function script_update(settings)
    custom_output_dir = obs.obs_data_get_string(settings, "custom_output_dir")
    folder_naming = obs.obs_data_get_string(settings, "folder_naming")
    if folder_naming ~= "video" then folder_naming = "timestamp" end
    export_txt = read_bool_setting(settings, "export_txt", export_txt)
    export_csv = read_bool_setting(settings, "export_csv", export_csv)
    export_xml = read_bool_setting(settings, "export_xml", export_xml)
    export_fcpxml = read_bool_setting(settings, "export_fcpxml", export_fcpxml)
    export_json = read_bool_setting(settings, "export_json", export_json)
    write_config()
end

function script_defaults(settings)
    obs.obs_data_set_default_string(settings, "custom_output_dir", "")
    obs.obs_data_set_default_string(settings, "folder_naming", "timestamp")
    obs.obs_data_set_default_bool(settings, "export_txt", true)
    obs.obs_data_set_default_bool(settings, "export_csv", true)
    obs.obs_data_set_default_bool(settings, "export_xml", true)
    obs.obs_data_set_default_bool(settings, "export_fcpxml", true)
    obs.obs_data_set_default_bool(settings, "export_json", true)
end

function script_load(settings)
    local win_dir = get_script_dir()

    -- Single-instance guard: reuse a healthy server on the saved port or
    -- anywhere in 8765-8770; launch the daemon only if all probes fail.
    if not find_active_port() then
        -- Start python server silently via VBS without blocking OBS
        os.execute('start "" wscript.exe "' .. win_dir .. 'run_silent.vbs"')
    end

    -- Register global OBS hotkey: appears in Settings -> Hotkeys -> "Marker Tool: Freeze Timestamp"
    hotkey_id = obs.obs_hotkey_register_frontend("marker_tool.freeze", "Marker Tool: Freeze Timestamp", trigger_freeze)
    local hotkey_save_array = obs.obs_data_get_array(settings, "marker_tool.freeze")
    obs.obs_hotkey_load(hotkey_id, hotkey_save_array)
    obs.obs_data_array_release(hotkey_save_array)

    -- Read initial settings
    custom_output_dir = obs.obs_data_get_string(settings, "custom_output_dir")
    folder_naming = obs.obs_data_get_string(settings, "folder_naming")
    if folder_naming ~= "video" then folder_naming = "timestamp" end
    export_txt = read_bool_setting(settings, "export_txt", export_txt)
    export_csv = read_bool_setting(settings, "export_csv", export_csv)
    export_xml = read_bool_setting(settings, "export_xml", export_xml)
    export_fcpxml = read_bool_setting(settings, "export_fcpxml", export_fcpxml)
    export_json = read_bool_setting(settings, "export_json", export_json)
    write_config()
end

function script_save(settings)
    -- Save hotkey configuration
    local hotkey_save_array = obs.obs_hotkey_save(hotkey_id)
    obs.obs_data_set_array(settings, "marker_tool.freeze", hotkey_save_array)
    obs.obs_data_array_release(hotkey_save_array)

    -- Save directory + naming + export properties
    obs.obs_data_set_string(settings, "custom_output_dir", custom_output_dir)
    obs.obs_data_set_string(settings, "folder_naming", folder_naming)
    obs.obs_data_set_bool(settings, "export_txt", export_txt)
    obs.obs_data_set_bool(settings, "export_csv", export_csv)
    obs.obs_data_set_bool(settings, "export_xml", export_xml)
    obs.obs_data_set_bool(settings, "export_fcpxml", export_fcpxml)
    obs.obs_data_set_bool(settings, "export_json", export_json)
    write_config()
end

function script_unload()
    local win_dir = get_script_dir()
    -- Cleanly terminate server on port 8765
    os.execute('cmd.exe /c "' .. win_dir .. 'stop.bat"')
end
