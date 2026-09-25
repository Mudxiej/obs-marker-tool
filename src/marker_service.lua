-- OBS Marker Server Auto-Lifecycle & Properties Script
local obs = obslua

local hotkey_id = obs.OBS_INVALID_HOTKEY_ID
local custom_output_dir = ""

function script_description()
    return "OBS Marker Tool Service\n\n" ..
           "• Save Folder: Default saves alongside your OBS recordings (next to video files). Use the property below to set a custom folder.\n" ..
           "• Global Hotkey: Go to OBS Settings -> Hotkeys and search for 'Marker Tool: Freeze Timestamp'. Bind F8 or any key combination!\n" ..
           "• Server Lifecycle: Automatically started when OBS launches, safely terminated when OBS exits."
end

local function get_script_dir()
    local dir = script_path()
    return string.gsub(dir, "/", "\\")
end

local function write_config()
    local win_dir = get_script_dir()
    local config_file = win_dir .. "config.json"
    local f = io.open(config_file, "w")
    if f then
        local safe_dir = string.gsub(custom_output_dir, "\\", "\\\\")
        f:write('{"custom_output_dir": "' .. safe_dir .. '"}')
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

local function on_open_folder(props, prop)
    if custom_output_dir ~= nil and custom_output_dir ~= "" then
        os.execute('start "" explorer.exe "' .. custom_output_dir .. '"')
    else
        os.execute('start "" curl.exe -s http://127.0.0.1:8765/api/open_folder')
    end
    return true
end

function script_properties()
    local props = obs.obs_properties_create()

    -- 1. Output directory property
    obs.obs_properties_add_path(props, "custom_output_dir", "Save Location (Leave blank for OBS Recording folder)", obs.OBS_PATH_DIRECTORY, "", "")

    -- 2. Open folder button
    obs.obs_properties_add_button(props, "btn_open", "Open Save Folder in Explorer", on_open_folder)

    return props
end

function script_update(settings)
    custom_output_dir = obs.obs_data_get_string(settings, "custom_output_dir")
    write_config()
end

function script_defaults(settings)
    obs.obs_data_set_default_string(settings, "custom_output_dir", "")
end

function script_load(settings)
    local win_dir = get_script_dir()

    -- Start python server silently via VBS without blocking OBS
    os.execute('start "" wscript.exe "' .. win_dir .. 'run_silent.vbs"')

    -- Register global OBS hotkey: appears in Settings -> Hotkeys -> "Marker Tool: Freeze Timestamp"
    hotkey_id = obs.obs_hotkey_register_frontend("marker_tool.freeze", "Marker Tool: Freeze Timestamp", trigger_freeze)
    local hotkey_save_array = obs.obs_data_get_array(settings, "marker_tool.freeze")
    obs.obs_hotkey_load(hotkey_id, hotkey_save_array)
    obs.obs_data_array_release(hotkey_save_array)

    -- Read initial settings
    custom_output_dir = obs.obs_data_get_string(settings, "custom_output_dir")
    write_config()
end

function script_save(settings)
    -- Save hotkey configuration
    local hotkey_save_array = obs.obs_hotkey_save(hotkey_id)
    obs.obs_data_set_array(settings, "marker_tool.freeze", hotkey_save_array)
    obs.obs_data_array_release(hotkey_save_array)

    -- Save directory property
    obs.obs_data_set_string(settings, "custom_output_dir", custom_output_dir)
    write_config()
end

function script_unload()
    local win_dir = get_script_dir()
    -- Cleanly terminate server on port 8765
    os.execute('cmd.exe /c "' .. win_dir .. 'stop.bat"')
end
