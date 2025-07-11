/*

	This file is part of OpenWebRX,
	an open-source SDR receiver software with a web UI.
	Copyright (c) 2013-2015 by Andras Retzler <randras@sdr.hu>
	Copyright (c) 2019-2021 by Jakob Ketterl <dd5jfk@darc.de>
	Copyright (c) 2022-2024 by Marat Fayzullin <luarvique@gmail.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

*/

is_firefox = navigator.userAgent.indexOf("Firefox") >= 0;

var bandwidth;
var center_freq;
var fft_size;
var fft_compression = "none";
var fft_codec;
var waterfall_setup_done = 0;
var secondary_fft_size;
var tuning_step_default = 1;
var tuning_step = 1;
var spectrum = null;
var bandplan = null;
var scanner = null;
var bookmarks = null;
var audioEngine = null;
var wf_data = null;

function zoomInOneStep() {
    zoom_set(zoom_level + 1);
}

function zoomOutOneStep() {
    zoom_set(zoom_level - 1);
}

function zoomInTotal() {
    zoom_set(zoom_levels.length - 1);
}

function zoomOutTotal() {
    zoom_set(0);
}

function tuneBySteps(steps) {
    steps = Math.round(steps);
    if (steps != 0) {
        UI.setOffsetFrequency(UI.getOffsetFrequency() + steps * tuning_step);
    }
}

function tuneBySquelch(dir) {
    // Must have a copy of the last received waterfall
    if (wf_data == null) return;

    // Get current squelch threshold from the slider
    // (why do we need to subtract ~13dB here to make FFT match the S-meter?)
    var $slider = $('#openwebrx-panel-receiver .openwebrx-squelch-slider');
    var squelch = $slider.val() - 13.0;

    // Start from the current offset within the waterfall
    var f = UI.getOffsetFrequency();

    // Scan up or down the waterfall
    dir = tuning_step * (dir>=0? 1 : -1);
    for(f += dir ; ; f += dir) {
        var i = Math.round(wf_data.length * (f / bandwidth + 0.5));
        if (i < 0 || i >= wf_data.length) {
            break;
        } else if (wf_data[i] >= squelch) {
            UI.setOffsetFrequency(f);
            break;
        }
    }
}

function monitorLevels(data) {
    if (wf_data == null || wf_data.length != data.length) {
        wf_data = data;
    } else {
        for (var j = 0 ; j < data.length ; j++) {
            if (data[j] >= wf_data[j]) {
                wf_data[j] = data[j];
            } else {
                wf_data[j] += (data[j] - wf_data[j]) / 5.0;
            }
        }
    }
}

function jumpBySteps(steps) {
    steps = Math.round(steps);
    if (steps != 0) {
        var key = UI.getDemodulatorPanel().getMagicKey();
        var f = center_freq + steps * bandwidth / 4;
        ws.send(JSON.stringify({
            "type": "setfrequency", "params": { "frequency": f, "key": key }
        }));
    }
}

function setSmeterRelativeValue(value) {
    if (value < 0) value = 0;
    if (value > 1.0) value = 1.0;
    var $meter = $("#openwebrx-smeter");
    var $bar = $meter.find(".openwebrx-smeter-bar");
    $bar.css({transform: 'translate(' + ((value - 1) * 100) + '%) translateZ(0)'});
    if (value > 0.9) {
        // red
        $bar.css({background: 'linear-gradient(to top, #ff5939 , #961700)'});
    } else if (value > 0.7) {
        // yellow
        $bar.css({background: 'linear-gradient(to top, #fff720 , #a49f00)'});
    } else {
        // red
        $bar.css({background: 'linear-gradient(to top, #22ff2f , #008908)'});
    }
}

function setSquelchSliderBackground(val) {
    var $slider = $('#openwebrx-panel-receiver .openwebrx-squelch-slider');
    var min = Number($slider.attr('min'));
    var max = Number($slider.attr('max'));
    var sliderPosition = $slider.val();
    var relative = (val - min) / (max - min);
    // use a brighter color when squelch is open
    var color = val >= sliderPosition ? '#22ff2f' : '#008908';
    // we don't use the gradient, but separate the colors discretely using css tricks
    var style = 'linear-gradient(90deg, ' + color + ', ' + color + ' ' + relative * 100 + '%, #B6B6B6 ' + relative * 100 + '%)';
    $slider.css('--track-background', style);
}

function getLogSmeterValue(value) {
    return 10 * Math.log10(value);
}

function setSmeterAbsoluteValue(value) //the value that comes from `csdr squelch_and_smeter_cc`
{
    var logValue = getLogSmeterValue(value);
    var levels = Waterfall.getRange();
    var percent = (logValue - (levels.min - 20)) / ((levels.max + 20) - (levels.min - 20));
    setSquelchSliderBackground(logValue);
    setSmeterRelativeValue(percent);
    $("#openwebrx-smeter-db").html(logValue.toFixed(1) + " dB");
}

function typeInAnimation(element, timeout, what, onFinish) {
    if (!what) {
        onFinish();
        return;
    }
    element.innerHTML += what[0];
    window.setTimeout(function () {
        typeInAnimation(element, timeout, what.substring(1), onFinish);
    }, timeout);
}


// ========================================================
// ================  DEMODULATOR ROUTINES  ================
// ========================================================

function getDemodulators() {
    return [ UI.getDemodulator() ].filter(function(d) { return !!d; });
}

function mkenvelopes(visible_range) //called from mkscale
{
    var demodulators = getDemodulators();
    scale_ctx.clearRect(0, 0, scale_ctx.canvas.width, 22); //clear the upper part of the canvas (where filter envelopes reside)
    for (var i = 0; i < demodulators.length; i++) {
        demodulators[i].envelope.draw(visible_range);
    }
    if (demodulators.length) {
        var bandpass = demodulators[0].getBandpass();
        secondary_demod_waterfall_set_zoom(bandpass.low_cut, bandpass.high_cut);
    }
}

function waterfallWidth() {
    return $('body').width();
}


// ========================================================
// ===================  SCALE ROUTINES  ===================
// ========================================================

var scale_ctx;
var scale_canvas;

function scale_setup() {
    scale_canvas = $("#openwebrx-scale-canvas")[0];
    scale_ctx = scale_canvas.getContext("2d");
    scale_canvas.addEventListener("mousedown", scale_canvas_mousedown, false);
    scale_canvas.addEventListener("mousemove", scale_canvas_mousemove, false);
    scale_canvas.addEventListener("mouseup", scale_canvas_mouseup, false);
    scale_canvas.addEventListener("wheel", scale_canvas_mousewheel, false);
    scale_canvas.addEventListener("touchmove", process_touch, false);
    scale_canvas.addEventListener("touchend", process_touch, false);
    scale_canvas.addEventListener("touchstart", process_touch, false);
    resize_scale();
    var frequency_container = $("#openwebrx-frequency-container");
    frequency_container.on("mousemove", frequency_container_mousemove, false);
}

var scale_canvas_drag_params = {
    mouse_down: false,
    mouse2_down: false,
    drag: false,
    start_x: 0,
    key_modifiers: {shiftKey: false, altKey: false, ctrlKey: false}
};

function scale_canvas_mousedown(evt) {
    // Left button only
    if (evt.button == 0) {
        scale_canvas_drag_params.mouse_down = true;
        scale_canvas_drag_params.drag = false;
        scale_canvas_drag_params.start_x = evt.pageX;
        scale_canvas_drag_params.key_modifiers.shiftKey = evt.shiftKey;
        scale_canvas_drag_params.key_modifiers.altKey = evt.altKey;
        scale_canvas_drag_params.key_modifiers.ctrlKey = evt.ctrlKey;
    } else {
        // Other buttons
        scale_canvas_drag_params.mouse2_down = true;
    }

    evt.preventDefault();
}

function scale_offset_freq_from_px(x, visible_range) {
    if (typeof visible_range === "undefined") visible_range = get_visible_freq_range();

    var f = (visible_range.start + visible_range.bw * (x / waterfallWidth())) - center_freq;

    if (tuning_step <= 0) {
        return f;
    } else {
        f = Math.round((center_freq + f) / tuning_step) * tuning_step;
        return f - center_freq;
    }
}

function scale_canvas_mousemove(evt) {
    var event_handled = false;
    var i;
    var demodulators = getDemodulators();
    if (scale_canvas_drag_params.mouse_down && !scale_canvas_drag_params.drag && Math.abs(evt.pageX - scale_canvas_drag_params.start_x) > canvas_drag_min_delta)
    //we can use the main drag_min_delta thing of the main canvas
    {
        scale_canvas_drag_params.drag = true;
        //call the drag_start for all demodulators (and they will decide if they're dragged, based on X coordinate)
        for (i = 0; i < demodulators.length; i++) event_handled |= demodulators[i].envelope.drag_start(evt.pageX, scale_canvas_drag_params.key_modifiers);
        scale_canvas.style.cursor = "move";
    }
    else if (scale_canvas_drag_params.drag) {
        //call the drag_move for all demodulators (and they will decide if they're dragged)
        for (i = 0; i < demodulators.length; i++) event_handled |= demodulators[i].envelope.drag_move(evt.pageX);
        if (!event_handled) demodulators[0].set_offset_frequency(scale_offset_freq_from_px(evt.pageX));
    }
}

function frequency_container_mousemove(evt) {
    var frequency = center_freq + scale_offset_freq_from_px(evt.pageX);
    UI.getDemodulatorPanel().setMouseFrequency(frequency);
}

function scale_canvas_end_drag(x) {
    scale_canvas.style.cursor = "default";
    scale_canvas_drag_params.drag = false;
    scale_canvas_drag_params.mouse_down = false;
    var event_handled = false;
    var demodulators = getDemodulators();
    for (var i = 0; i < demodulators.length; i++) event_handled |= demodulators[i].envelope.drag_end();
    if (!event_handled) {
        demodulators[0].set_offset_frequency(scale_offset_freq_from_px(x));
        UI.toggleScanner(false);
    }
}

function scale_canvas_mouseup(evt) {
    if (evt.button == 0)
        scale_canvas_end_drag(evt.pageX);
    else
        scale_canvas_drag_params.mouse2_down = false;
}

function scale_canvas_mousewheel(evt) {
    var dir = (evt.deltaY / Math.abs(evt.deltaY)) > 0;
    var adjustWidth = scale_canvas_drag_params.mouse2_down || evt.shiftKey;
    var demodulators = getDemodulators();
    var event_handled = false;
    for (var i = 0; i < demodulators.length; i++) event_handled |= demodulators[i].envelope.wheel(evt.pageX, dir, adjustWidth);
    // If not handled by demodulators, default to tuning or zooming
    if (!event_handled) canvas_mousewheel(evt);
}

function scale_px_from_freq(f, range) {
    return Math.round(((f - range.start) / range.bw) * waterfallWidth());
}

function get_visible_freq_range() {
    if (!bandwidth) return false;
    var fcalc = function (x) {
        var canvasWidth = waterfallWidth() * zoom_levels[zoom_level];
        return Math.round(((-zoom_offset_px + x) / canvasWidth) * bandwidth) + (center_freq - bandwidth / 2);
    };
    var out = {
        start: fcalc(0),
        center: fcalc(waterfallWidth() / 2),
        end: fcalc(waterfallWidth()),
    }
    out.bw = out.end - out.start;
    out.hps = out.bw / waterfallWidth();
    return out;
}

var scale_markers_levels = [
    {
        "large_marker_per_hz": 10000000, //large
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 0
    },
    {
        "large_marker_per_hz": 5000000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 0
    },
    {
        "large_marker_per_hz": 1000000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 0
    },
    {
        "large_marker_per_hz": 500000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 1
    },
    {
        "large_marker_per_hz": 100000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 1
    },
    {
        "large_marker_per_hz": 50000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 2
    },
    {
        "large_marker_per_hz": 10000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 2
    },
    {
        "large_marker_per_hz": 5000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 3
    },
    {
        "large_marker_per_hz": 1000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 1
    }
];
var scale_min_space_bw_texts = 50;
var scale_min_space_bw_small_markers = 7;

function get_scale_mark_spacing(range) {
    var out = {};
    var fcalc = function (freq) {
        out.numlarge = (range.bw / freq);
        out.large = waterfallWidth() / out.numlarge; 	//distance between large markers (these have text)
        out.ratio = 5; 														//(ratio-1) small markers exist per large marker
        out.small = out.large / out.ratio; 								//distance between small markers
        if (out.small < scale_min_space_bw_small_markers) return false;
        if (out.small / 2 >= scale_min_space_bw_small_markers && freq.toString()[0] !== "5") {
            out.small /= 2;
            out.ratio *= 2;
        }
        out.smallbw = freq / out.ratio;
        return true;
    };
    for (var i = scale_markers_levels.length - 1; i >= 0; i--) {
        var mp = scale_markers_levels[i];
        if (!fcalc(mp.large_marker_per_hz)) continue;
        //console.log(mp.large_marker_per_hz);
        //console.log(out);
        if (out.large - mp.estimated_text_width > scale_min_space_bw_texts) break;
    }
    out.params = mp;
    return out;
}

var range;

function mkscale() {
    //clear the lower part of the canvas (where frequency scale resides; the upper part is used by filter envelopes):
    range = get_visible_freq_range();
    if (!range) return;
    mkenvelopes(range); //when scale changes we will always have to redraw filter envelopes, too
    scale_ctx.clearRect(0, 22, scale_ctx.canvas.width, scale_ctx.canvas.height - 22);
    scale_ctx.strokeStyle = "#fff";
    scale_ctx.font = "bold 11px sans-serif";
    scale_ctx.textBaseline = "top";
    scale_ctx.fillStyle = "#fff";
    var spacing = get_scale_mark_spacing(range);
    //console.log(spacing);
    var marker_hz = Math.ceil(range.start / spacing.smallbw) * spacing.smallbw;
    var text_h_pos = 22 + 10 + ((is_firefox) ? 3 : 0);
    var text_to_draw = '';
    var ftext = function (f) {
        text_to_draw = format_frequency(spacing.params.format, f, spacing.params.pre_divide, spacing.params.decimals);
    };
    var last_large;
    var x;
    while ((x = scale_px_from_freq(marker_hz, range)) <= window.innerWidth) {
        scale_ctx.beginPath();
        scale_ctx.moveTo(x, 22);
        if (marker_hz % spacing.params.large_marker_per_hz === 0) {  //large marker
            if (typeof first_large === "undefined") var first_large = marker_hz;
            last_large = marker_hz;
            scale_ctx.lineWidth = 3.5;
            scale_ctx.lineTo(x, 22 + 11);
            ftext(marker_hz);
            var text_measured = scale_ctx.measureText(text_to_draw);
            scale_ctx.textAlign = "center";
            //advanced text drawing begins
            if (zoom_level === 0 && (range.start + spacing.smallbw * spacing.ratio > marker_hz) && (x < text_measured.width / 2)) { //if this is the first overall marker when zoomed out...                  and if it would be clipped off the screen...
                if (scale_px_from_freq(marker_hz + spacing.smallbw * spacing.ratio, range) - text_measured.width >= scale_min_space_bw_texts) { //and if we have enough space to draw it correctly without clipping
                    scale_ctx.textAlign = "left";
                    scale_ctx.fillText(text_to_draw, 0, text_h_pos);
                }
            }
            else if (zoom_level === 0 && (range.end - spacing.smallbw * spacing.ratio < marker_hz) && (x > window.innerWidth - text_measured.width / 2)) { //     if this is the last overall marker when zoomed out...                 and if it would be clipped off the screen...
                if (window.innerWidth - text_measured.width - scale_px_from_freq(marker_hz - spacing.smallbw * spacing.ratio, range) >= scale_min_space_bw_texts) { //and if we have enough space to draw it correctly without clipping
                    scale_ctx.textAlign = "right";
                    scale_ctx.fillText(text_to_draw, window.innerWidth, text_h_pos);
                }
            }
            else scale_ctx.fillText(text_to_draw, x, text_h_pos); //draw text normally
        }
        else {  //small marker
            scale_ctx.lineWidth = 2;
            scale_ctx.lineTo(x, 22 + 8);
        }
        marker_hz += spacing.smallbw;
        scale_ctx.stroke();
    }
    if (zoom_level !== 0) { // if zoomed, we don't want the texts to disappear because their markers can't be seen
        // on the left side
        scale_ctx.textAlign = "center";
        var f = first_large - spacing.smallbw * spacing.ratio;
        x = scale_px_from_freq(f, range);
        ftext(f);
        var w = scale_ctx.measureText(text_to_draw).width;
        if (x + w / 2 > 0) scale_ctx.fillText(text_to_draw, x, 22 + 10);
        // on the right side
        f = last_large + spacing.smallbw * spacing.ratio;
        x = scale_px_from_freq(f, range);
        ftext(f);
        w = scale_ctx.measureText(text_to_draw).width;
        if (x - w / 2 < window.innerWidth) scale_ctx.fillText(text_to_draw, x, 22 + 10);
    }
}

function resize_scale() {
    var ratio = window.devicePixelRatio || 1;
    var w = window.innerWidth;
    var h = 47;
    scale_canvas.style.width = w + "px";
    scale_canvas.style.height = h + "px";
    w *= ratio;
    h *= ratio;
    scale_canvas.width = w;
    scale_canvas.height = h;
    scale_ctx.scale(ratio, ratio);
    mkscale();
    bandplan.draw();
    bookmarks.position();
}

function format_frequency(format, freq_hz, pre_divide, decimals) {
    var out = format.replace("{x}", (freq_hz / pre_divide).toFixed(decimals));
    var at = out.indexOf(".") + 4;
    while (decimals > 3) {
        out = out.substr(0, at) + "," + out.substr(at);
        at += 4;
        decimals -= 3;
    }
    return out;
}

var canvas_drag = false;
var canvas_drag_min_delta = 1;
var canvas_mouse_down = false;
var canvas_mouse2_down = 0;
var canvas_drag_last_x;
var canvas_drag_last_y;
var canvas_drag_start_x;
var canvas_drag_start_y;

var touch_id1 = -1;
var touch_id2 = -1;
var touch_zoom0;
var touch_dst0;

function process_touch(evt) {
    var t0 = null;
    var type = "";

    switch(evt.type)
    {
        case "touchstart":
            // Detect first finger
            if (touch_id1 < 0) {
                t0 = evt.changedTouches[0];
                touch_id1 = t0.identifier;
                type = "mousedown";
            }

            // Detect second finger
            if ((touch_id1 >= 0) && (touch_id2 < 0)) {
                for (var j=0 ; j<evt.changedTouches.length ; ++j) {
                    if (evt.changedTouches[j].identifier != touch_id1) {
                        var t2 = evt.changedTouches[j];
                        // Find the existing first finger
                        for (var i=0 ; i<evt.touches.length ; ++i) {
                            // If both fingers found...
                            if (evt.touches[i].identifier == touch_id1) {
                                // Initialize initial distance & zoom level
                                var t1 = evt.touches[i];
                                touch_zoom0 = zoom_level;
                                touch_dst0  = Math.abs(t2.clientX - t1.clientX);
                                touch_id2   = t2.identifier;
                                break;
                            }
                        }
                        break;
                    }
                }
            }
            break;

        case "touchmove":
            // Check if first finger moved
            if (touch_id1 >= 0) {
                for (var j=0 ; j<evt.changedTouches.length ; ++j) {
                    if (evt.changedTouches[j].identifier == touch_id1) {
                        t0 = evt.changedTouches[j];
                        type = "mousemove";
                        break;
                    }
                }
            }

            // If using two fingers...
            if ((touch_id1 >= 0) && (touch_id2 >= 0) && (touch_dst0 > 0)) {
                var t1 = null;
                var t2 = null;
                // If first finger changed...
                if (t0 != null) {
                    // Reuse found first finger
                    t1 = t0;
                    // Find the second finger
                    for (var j=0 ; j<evt.touches.length ; ++j) {
                        if (evt.touches[j].identifier == touch_id2) {
                            t2 = evt.touches[j];
                            break;
                        }
                    }
                } else for (var j=0 ; j<evt.changedTouches.length ; ++j) {
                    if (evt.changedTouches[j].identifier == touch_id2) {
                        // Second finger change found
                        t2 = evt.changedTouches[j];
                        // Find the first finger
                        for (var i=0 ; i<evt.touches.length ; ++i) {
                            if (evt.touches[i].identifier == touch_id1) {
                                t1 = evt.touches[i];
                                break;
                            }
                        }
                    }
                }
                // If both fingers found...
                if ((t1 != null) && (t2 != null)) {
                    // Zoom by distance ratio
                    var dst = Math.abs(t2.clientX - t1.clientX);
                    if (dst >= touch_dst0) {
                        zoom_set(touch_zoom0 + Math.round(dst / touch_dst0) - 1);
                    } else {
                        zoom_set(touch_zoom0 - Math.round(touch_dst0 / dst) + 1);
                    }
                    // Cancel mouse movement
                    t0 = null;
                }
            }
            break;

        case "touchend":
            // Check if first finger went up
            if (touch_id1 >= 0) {
                for (var j=0 ; j<evt.changedTouches.length ; ++j) {
                    if (evt.changedTouches[j].identifier == touch_id1) {
                        t0 = (touch_id2<0)? evt.changedTouches[j] : null;
                        touch_id1 = -1;
                        touch_id2 = -1;
                        type = "mouseup";
                        break;
                    }
                }
            }

            // Check if second finger went up
            if (touch_id2 >= 0) {
                for (var j=0 ; j<evt.changedTouches.length ; ++j) {
                    if (evt.changedTouches[j].identifier == touch_id2) {
                        t0 = null;
                        touch_id1 = -1;
                        touch_id2 = -1;
                        break;
                    }
                }
            }
    }

    // If first finger has changed its state, simulate mouse event
    if (t0 != null) {
        var mouseEvt = document.createEvent("MouseEvent");

        mouseEvt.initMouseEvent(type,
            true, true, window, 1, t0.screenX, t0.screenY,
            t0.clientX, t0.clientY, false, false, false,
            false, 0/*left*/, null);

        t0.target.dispatchEvent(mouseEvt);
        evt.preventDefault();
    }
}

function canvas_mousedown(evt) {
    if (evt.button > 0) {
        if (canvas_mouse2_down == 0)
            canvas_mouse2_down = evt.button;
    } else {
        canvas_mouse_down = true;
        canvas_drag = false;
        canvas_drag_last_x = canvas_drag_start_x = evt.pageX;
        canvas_drag_last_y = canvas_drag_start_y = evt.pageY;
    }

    evt.preventDefault(); //don't show text selection mouse pointer
}

function canvas_mousemove(evt) {
    if (!waterfall_setup_done) return;
    var relativeX = get_relative_x(evt);
    if (!canvas_mouse_down) {
        UI.getDemodulatorPanel().setMouseFrequency(UI.getFrequency(relativeX));
    } else {
        if (!canvas_drag && Math.abs(evt.pageX - canvas_drag_start_x) > canvas_drag_min_delta) {
            canvas_drag = true;
            canvas_container.style.cursor = "move";
        }
        if (canvas_drag) {
            var deltaX = canvas_drag_last_x - evt.pageX;
            var dpx = range.hps * deltaX;

            if (
                !(zoom_center_rel + dpx > (bandwidth / 2 - waterfallWidth() * (1 - zoom_center_where) * range.hps)) &&
                !(zoom_center_rel + dpx < -bandwidth / 2 + waterfallWidth() * zoom_center_where * range.hps)
            ) {
                zoom_center_rel += dpx;
            }
            resize_canvases(false);
            mkscale();
            bandplan.draw();
            bookmarks.position();

            canvas_drag_last_x = evt.pageX;
            canvas_drag_last_y = evt.pageY;
        }
    }
}

function canvas_container_mouseleave() {
    canvas_end_drag();
}

function canvas_mouseup(evt) {
    if (evt.button > 0) {
        if (evt.button == canvas_mouse2_down)
            canvas_mouse2_down = 0;
    } else {
        if (!waterfall_setup_done) return;
        var relativeX = get_relative_x(evt);

        if (!canvas_drag) {
            var f = UI.getOffsetFrequency(relativeX);
            // For CW, move offset 800Hz below the actual carrier
            if (UI.getModulation() === 'cw') f = f - 800;
            UI.setOffsetFrequency(f);
            UI.toggleScanner(false);
        } else {
            canvas_end_drag();
        }
        canvas_mouse_down = false;
    }
}

function canvas_end_drag() {
    canvas_container.style.cursor = "crosshair";
    canvas_mouse_down = false;
}

function zoom_center_where_calc(screenposX) {
    return screenposX / waterfallWidth();
}

function get_relative_x(evt) {
    var relativeX = evt.offsetX || evt.layerX;
    if ($(evt.target).closest(canvas_container).length) return relativeX;
    // compensate for the frequency scale, since that is not resized by the browser.
    var relatives = $(evt.target).closest('#openwebrx-frequency-container').map(function(){
        return evt.pageX - this.offsetLeft;
    });
    if (relatives.length) relativeX = relatives[0];

    return relativeX - zoom_offset_px;
}

function canvas_mousewheel(evt) {
    if (!waterfall_setup_done) return;
    var relativeX = get_relative_x(evt);
    var dir = (evt.deltaY / Math.abs(evt.deltaY)) > 0;

    // Zoom when mouse button down, tune otherwise
    // (optionally, invert this behavior)
    var zoom_me = (canvas_mouse2_down > 0) || evt.shiftKey?
        !UI.getWheelSwap() : UI.getWheelSwap();
    if (zoom_me) {
        zoom_step(dir, relativeX, zoom_center_where_calc(evt.pageX));
    } else {
        tuneBySteps(dir? -1:1);
    }

    evt.preventDefault();
}


var zoom_max_level_hps = 33; //Hz/pixel
var zoom_levels_count = 14;

function get_zoom_coeff_from_hps(hps) {
    var shown_bw = (window.innerWidth * hps);
    return bandwidth / shown_bw;
}

var zoom_levels = [1];
var zoom_level = 0;
var zoom_offset_px = 0;
var zoom_center_rel = 0;
var zoom_center_where = 0;

var smeter_level = 0;

function mkzoomlevels() {
    zoom_levels = [1];
    var maxc = get_zoom_coeff_from_hps(zoom_max_level_hps);
    if (maxc < 1) return;
    // logarithmic interpolation
    var zoom_ratio = Math.pow(maxc, 1 / zoom_levels_count);
    for (var i = 1; i < zoom_levels_count; i++)
        zoom_levels.push(Math.pow(zoom_ratio, i));
}

function zoom_step(out, where, onscreen) {
    if ((out && zoom_level === 0) || (!out && zoom_level >= zoom_levels_count - 1)) return;
    if (out) --zoom_level;
    else ++zoom_level;

    zoom_center_rel = UI.getOffsetFrequency(where);
    //console.log("zoom_step || zlevel: "+zoom_level.toString()+" zlevel_val: "+zoom_levels[zoom_level].toString()+" zoom_center_rel: "+zoom_center_rel.toString());
    zoom_center_where = onscreen;
    //console.log(zoom_center_where, zoom_center_rel, where);
    resize_canvases(true);
    mkscale();
    bandplan.draw();
    bookmarks.position();
}

function zoom_set(level) {
    if (!(level >= 0 && level <= zoom_levels.length - 1)) return;
    level = parseInt(level);
    zoom_level = level;
    //zoom_center_rel=UI.getOffsetFrequency(-canvases[0].offsetLeft+waterfallWidth()/2); //zoom to screen center instead of demod envelope
    var demodulator = UI.getDemodulator();
    zoom_center_rel = demodulator != null? demodulator.get_offset_frequency() : 0;
    zoom_center_where = 0.5 + (zoom_center_rel / bandwidth); //this is a kind of hack
    resize_canvases(true);
    mkscale();
    bandplan.draw();
    bookmarks.position();
}

function zoom_calc() {
    var winsize = waterfallWidth();
    var canvases_new_width = winsize * zoom_levels[zoom_level];
    zoom_offset_px = -((canvases_new_width * (0.5 + zoom_center_rel / bandwidth)) - (winsize * zoom_center_where));
    if (zoom_offset_px > 0) zoom_offset_px = 0;
    if (zoom_offset_px < winsize - canvases_new_width)
        zoom_offset_px = winsize - canvases_new_width;
}

var networkSpeedMeasurement;
var currentprofile = {
    toString: function() {
        return this['sdr_id'] + '|' + this['profile_id'];
    }
};

var COMPRESS_FFT_PAD_N = 10; //should be the same as in csdr.c

function on_ws_recv(evt) {
    if (typeof evt.data === 'string') {
        // text messages
        networkSpeedMeasurement.add(evt.data.length);

        if (evt.data.substr(0, 16) === "CLIENT DE SERVER") {
            params = Object.fromEntries(
                evt.data.slice(17).split(' ').map(function(param) {
                    var args = param.split('=');
                    return [args[0], args.slice(1).join('=')]
                })
            );
            var versionInfo = 'Unknown server';
            if (params.server && params.server === 'openwebrx' && params.version) {
                versionInfo = 'OpenWebRX+ version: ' + params.version;
            }
            divlog('Server acknowledged WebSocket connection, ' + versionInfo);
        } else {
            try {
                var json = JSON.parse(evt.data);
                switch (json.type) {
                    case "config":
                        var config = json['value'];

                        // Configure waterfall min/max levels, etc
                        Waterfall.configure(config);

                        if ('waterfall_colors' in config)
                            UI.setDefaultWfTheme(config['waterfall_colors']);

                        var initial_demodulator_params = {};
                        if ('start_mod' in config)
                            initial_demodulator_params['mod'] = config['start_mod'];
                        if ('start_offset_freq' in config)
                            initial_demodulator_params['offset_frequency'] = config['start_offset_freq'];
                        if ('initial_squelch_level' in config)
                            initial_demodulator_params['squelch_level'] = Number.isInteger(config['initial_squelch_level']) ? config['initial_squelch_level'] : -150;

                        if ('samp_rate' in config)
                            bandwidth = config['samp_rate'];
                        if ('center_freq' in config)
                            center_freq = config['center_freq'];
                        if ('fft_size' in config) {
                            fft_size = config['fft_size'];
                            waterfall_clear();
                        }
                        if ('audio_compression' in config) {
                            var audio_compression = config['audio_compression'];
                            audioEngine.setCompression(audio_compression);
                            divlog("Audio stream is " + ((audio_compression === "adpcm") ? "compressed" : "uncompressed") + ".");
                        }
                        if ('fft_compression' in config) {
                            fft_compression = config['fft_compression'];
                            divlog("FFT stream is " + ((fft_compression === "adpcm") ? "compressed" : "uncompressed") + ".");
                        }
                        if ('max_clients' in config)
                            $('#openwebrx-bar-clients').progressbar().setMaxClients(config['max_clients']);

                        waterfall_init();

                        var demodulatorPanel = UI.getDemodulatorPanel();

                        demodulatorPanel.setCenterFrequency(center_freq);
                        demodulatorPanel.setInitialParams(initial_demodulator_params);

                        if ('squelch_auto_margin' in config)
                            demodulatorPanel.setSquelchMargin(config['squelch_auto_margin']);

                        bookmarks.loadLocalBookmarks();

                        if ('sdr_id' in config || 'profile_id' in config) {
                            currentprofile['sdr_id'] = config['sdr_id'] || currentprofile['sdr_id'];
                            currentprofile['profile_id'] = config['profile_id'] || currentprofile['profile_id'];
                            $('#openwebrx-sdr-profiles-listbox').val(currentprofile.toString());

                            UI.toggleScanner(false);
                            tuning_step_reset();
                            waterfall_clear();
                            zoom_set(0);
                        }

                        if ('sdr_id' in config || 'profile_id' in config || 'waterfall_levels' in config) {
                            Waterfall.setDefaultRange();
                        }

                        if ('tuning_precision' in config)
                            demodulatorPanel.setTuningPrecision(config['tuning_precision']);

                        if ('tuning_step' in config) {
                            tuning_step_default = config['tuning_step'];
                            tuning_step_reset();
                        }

                        if ('allow_audio_recording' in config) {
                            var x = config['allow_audio_recording'];
                            $('.openwebrx-record-button').css('display', x? '':'none');
                        }

                        if ('allow_chat' in config) {
                            var x = config['allow_chat'];
                            $('#openwebrx-chat-inputs').css('display', x? '':'none');
                            $('#openwebrx-chat-label').html(x? 'Chat':'Log');
                        }

                        if ('receiver_gps' in config) {
                            Utils.setReceiverPos(config['receiver_gps']);
                        }

                        if ('flight_url' in config) {
                            Utils.setFlightUrl(config['flight_url']);
                        }

                        if ('modes_url' in config) {
                            Utils.setIcaoUrl(config['modes_url']);
                        }

                        if ('callsign_url' in config) {
                            Utils.setCallsignUrl(config['callsign_url']);
                        }

                        if ('vessel_url' in config) {
                            Utils.setVesselUrl(config['vessel_url']);
                        }

                        // Load user interface settings from local storage
                        UI.loadSettings();
                        Chat.loadSettings();

                        // Initialize keyboard shortcuts
                        Shortcuts.init(document.body);

                        break;
                    case "secondary_config":
                        var s = json['value'];
                        secondary_fft_size = s['secondary_fft_size'] || secondary_fft_size;
                        secondary_bw = s['secondary_bw'] || secondary_bw;
                        if_samp_rate = s['if_samp_rate'] || if_samp_rate;
                        if (if_samp_rate) secondary_demod_init_canvases();
                        break;
                    case "receiver_details":
                        $('.webrx-top-container').header().setDetails(json['value']);
                        break;
                    case "smeter":
                        smeter_level = json['value'];
                        setSmeterAbsoluteValue(smeter_level);
                        break;
                    case "cpuusage":
                        $('#openwebrx-bar-server-cpu').progressbar().setUsage(json['value']);
                        break;
                    case "temperature":
                        $('#openwebrx-bar-server-cpu').progressbar().setTemp(json['value']);
                        break;
                    case "clients":
                        $('#openwebrx-bar-clients').progressbar().setClients(json['value']);
                        break;
                    case "bands":
                        // Feed bandplan display with data
                        bandplan.update(json['value']);
                        break;
                    case "profiles":
                        var listbox = $("#openwebrx-sdr-profiles-listbox");
                        listbox.html(json['value'].map(function (profile) {
                            return '<option value="' + profile['id'] + '">' + profile['name'] + "</option>";
                        }).join(""));
                        $('#openwebrx-sdr-profiles-listbox').val(currentprofile.toString());
                        // this is a bit hacky since it only makes sense if the error is actually "no sdr devices"
                        // the only other error condition for which the overlay is used right now is "too many users"
                        // so there shouldn't be a problem here
                        if (Object.keys(json['value']).length) {
                            $('#openwebrx-error-overlay').hide();
                        }
                        break;
                    case "features":
                        Modes.setFeatures(json['value']);
                        $('#openwebrx-panel-metadata-wfm').metaPanel().each(function() {
                            this.setEnabled(!!json.value.rds);
                        });
                        break;
                    case "metadata":
                        $('.openwebrx-meta-panel').metaPanel().each(function(){
                            this.update(json['value']);
                        });
                        break;
                    case "dial_frequencies":
                        var as_bookmarks = json['value'].map(function (d) {
                            return {
                                name: d['mode'].toUpperCase(),
                                modulation: d['mode'],
                                frequency: d['frequency'],
                                underlying: d['underlying']
                            };
                        });
                        bookmarks.replace_bookmarks(as_bookmarks, 'dial_frequencies');
                        break;
                    case "bookmarks":
                        bookmarks.replace_bookmarks(json['value'], "server");
                        break;
                    case "sdr_error":
                        divlog(json['value'], true);
                        var $overlay = $('#openwebrx-error-overlay');
                        $overlay.find('.errormessage').text(json['value']);
                        $overlay.show();
                        UI.getDemodulatorPanel().stopDemodulator();
                        break;
                    case "demodulator_error":
                        divlog(json['value'], true);
                        break;
                    case 'secondary_demod':
                        var value = json['value'];
                        var panels = ['wsjt', 'packet', 'pocsag', 'page', 'sstv', 'fax', 'ism', 'hfdl', 'adsb', 'dsc', 'cwskimmer'].map(function(id) {
                            return $('#openwebrx-panel-' + id + '-message')[id + 'MessagePanel']();
                        });
                        panels.push($('#openwebrx-panel-js8-message').js8());
                        if (!panels.some(function(panel) {
                            if (!panel.supportsMessage(value)) return false;
                            panel.pushMessage(value);
                            return true;
                        })) {
                            secondary_demod_push_data(value);
                        }
                        break;
                    case 'log_message':
                        divlog(json['value'], true);
                        break;
                    case 'chat_message':
                        Chat.recvMessage(json['name'], json['text'], json['color']);
                        break;
                    case 'backoff':
                        divlog("Server is currently busy: " + json['reason'], true);
                        var $overlay = $('#openwebrx-error-overlay');
                        $overlay.find('.errormessage').text(json['reason']);
                        $overlay.show();
                        // set a higher reconnection timeout right away to avoid additional load
                        reconnect_timeout = 16000;
                        break;
                    case 'modes':
                        Modes.setModes(json['value']);
                        break;
                    default:
                        console.warn('received message of unknown type: ' + json['type']);
                }
            } catch (e) {
                // don't lose exception
                console.error(e)
            }
        }
    } else if (evt.data instanceof ArrayBuffer) {
        // binary messages
        networkSpeedMeasurement.add(evt.data.byteLength);

        var type = new Uint8Array(evt.data, 0, 1)[0];
        var data = evt.data.slice(1);

        var waterfall_i16;
        var waterfall_f32;
        var i;

        switch (type) {
            case 1:
                // FFT data
                if (fft_compression === "none") {
                    waterfall_f32 = new Float32Array(data);
                } else if (fft_compression === "adpcm") {
                    fft_codec.reset();

                    waterfall_i16 = fft_codec.decode(new Uint8Array(data));
                    waterfall_f32 = new Float32Array(waterfall_i16.length - COMPRESS_FFT_PAD_N);
                    for (i = 0; i < waterfall_i16.length; i++) waterfall_f32[i] = waterfall_i16[i + COMPRESS_FFT_PAD_N] / 100;
                }
                // Feed waterfall display with data
                waterfall_add(waterfall_f32);
                // Feed spectrum display with data
                spectrum.update(waterfall_f32);
                // Feed scanner with data
                scanner.update(waterfall_f32);
                // Monitor waterfall levels for squelch-based tuning
                monitorLevels(waterfall_f32);
                break;
            case 2:
                // audio data
                audioEngine.pushAudio(data);
                break;
            case 3:
                // secondary FFT
                if (fft_compression === "none") {
                    secondary_demod_waterfall_add(new Float32Array(data));
                } else if (fft_compression === "adpcm") {
                    fft_codec.reset();

                    waterfall_i16 = fft_codec.decode(new Uint8Array(data));
                    waterfall_f32 = new Float32Array(waterfall_i16.length - COMPRESS_FFT_PAD_N);
                    for (i = 0; i < waterfall_i16.length; i++) waterfall_f32[i] = waterfall_i16[i + COMPRESS_FFT_PAD_N] / 100;
                    secondary_demod_waterfall_add(waterfall_f32);
                }
                break;
            case 4:
                // hd audio data
                audioEngine.pushHdAudio(data);
                break;
            default:
                console.warn('unknown type of binary message: ' + type)
        }
    }
}

function on_ws_opened() {
    $('#openwebrx-error-overlay').hide();
    ws.send("SERVER DE CLIENT client=openwebrx.js type=receiver");
    divlog("WebSocket opened to " + ws.url);
    if (!networkSpeedMeasurement) {
        networkSpeedMeasurement = new Measurement();
        networkSpeedMeasurement.report(60000, 1000, function(rate){
            $('#openwebrx-bar-network-speed').progressbar().setSpeed(rate);
        });
    } else {
        networkSpeedMeasurement.reset();
    }
    reconnect_timeout = false;
    ws.send(JSON.stringify({
        "type": "connectionproperties",
        "params": {
            "output_rate": audioEngine.getOutputRate(),
            "hd_output_rate": audioEngine.getHdOutputRate()
        }
    }));
}

var was_error = 0;

function divlog(what, is_error) {
    is_error = !!is_error;
    was_error |= is_error;
    if (is_error) {
        what = "<span class=\"webrx-error\">" + what + "</span>";
        toggle_panel("openwebrx-panel-log", true); //show panel if any error is present
    }
    $('#openwebrx-messages')[0].innerHTML += what + "<br />";
    var nano = $('#openwebrx-log-scroll');
    nano.nanoScroller();
    nano.nanoScroller({scroll: 'bottom'});
}

var volumeBeforeMute = 100.0;
var mute = false;

// Optimalise these if audio lags or is choppy:
var audio_buffer_maximal_length_sec = 1; //actual number of samples are calculated from sample rate

function onAudioStart(apiType){
    divlog('Web Audio API succesfully initialized, using ' + apiType  + ' API, sample rate: ' + audioEngine.getSampleRate() + " Hz");

    hideOverlay();

    // canvas_container is set after waterfall_init() has been called. we cannot initialize before.
    //if (canvas_container) synchronize_demodulator_init();

    //hide log panel in a second (if user has not hidden it yet)
    window.setTimeout(function () {
        toggle_panel("openwebrx-panel-log", !!was_error);
    }, 2000);

    // Load audio settings from local storage
    UI.loadAudioSettings();
}

var reconnect_timeout = false;

function on_ws_closed() {
    var demodulatorPanel = UI.getDemodulatorPanel();
    demodulatorPanel.stopDemodulator();
    demodulatorPanel.resetInitialParams();
    if (reconnect_timeout) {
        // max value: roundabout 8 and a half minutes
        reconnect_timeout = Math.min(reconnect_timeout * 2, 512000);
    } else {
        // initial value: 1s
        reconnect_timeout = 1000;
    }
    divlog("WebSocket has closed unexpectedly. Attempting to reconnect in " + reconnect_timeout / 1000 + " seconds...", 1);

    setTimeout(open_websocket, reconnect_timeout);
}

function on_ws_error() {
    divlog("WebSocket error.", 1);
}

var ws;

function open_websocket() {
    var protocol = window.location.protocol.match(/https/) ? 'wss' : 'ws';

    var href = window.location.href;
    var index = href.lastIndexOf('/');
    if (index > 0) {
        href = href.substr(0, index + 1);
    }
    href = href.split("://")[1];
    href = protocol + "://" + href;
    if (!href.endsWith('/')) {
        href += '/';
    }
    var ws_url = href + "ws/";

    if (!("WebSocket" in window))
        divlog("Your browser does not support WebSocket, which is required for WebRX to run. Please upgrade to a HTML5 compatible browser.");
    ws = new WebSocket(ws_url);
    ws.onopen = on_ws_opened;
    ws.onmessage = on_ws_recv;
    ws.onclose = on_ws_closed;
    ws.binaryType = "arraybuffer";
    window.onbeforeunload = function () { //http://stackoverflow.com/questions/4812686/closing-websocket-correctly-html5-javascript
        ws.onclose = function () {
        };
        ws.close();
    };
    ws.onerror = on_ws_error;
}

var canvas_context;
var canvases = [];
var canvas_default_height = 200;
var canvas_container;
var canvas_actual_line = -1;

function add_canvas() {
    var new_canvas = document.createElement("canvas");
    new_canvas.width = fft_size;
    new_canvas.height = canvas_default_height;
    canvas_actual_line = canvas_default_height;
    new_canvas.openwebrx_top = -canvas_default_height;
    new_canvas.style.transform = 'translate(0, ' + new_canvas.openwebrx_top.toString() + 'px)';
    canvas_context = new_canvas.getContext("2d");
    canvas_container.appendChild(new_canvas);
    canvases.push(new_canvas);
    while (canvas_container && canvas_container.clientHeight + canvas_default_height * 2 < canvases.length * canvas_default_height) {
        var c = canvases.shift();
        if (!c) break;
        canvas_container.removeChild(c);
    }
}


function init_canvas_container() {
    canvas_container = $("#webrx-canvas-container")[0];
    canvas_container.addEventListener("mouseleave", canvas_container_mouseleave, false);
    canvas_container.addEventListener("mousemove", canvas_mousemove, false);
    canvas_container.addEventListener("mouseup", canvas_mouseup, false);
    canvas_container.addEventListener("mousedown", canvas_mousedown, false);
    canvas_container.addEventListener("wheel", canvas_mousewheel, false);
    canvas_container.addEventListener("touchmove", process_touch, false);
    canvas_container.addEventListener("touchend", process_touch, false);
    canvas_container.addEventListener("touchstart", process_touch, false);
    var frequency_container = $("#openwebrx-frequency-container");
    frequency_container.on("wheel", canvas_mousewheel, false);
}

function shift_canvases() {
    canvases.forEach(function (p) {
        p.style.transform = 'translate(0, ' + (p.openwebrx_top++).toString() + 'px)';
    });
}

function resize_canvases(zoom) {
    if (typeof zoom === "undefined") zoom = false;
    if (!zoom) mkzoomlevels();
    zoom_calc();
    $('#webrx-canvas-container').css({
        width: waterfallWidth() * zoom_levels[zoom_level] + 'px',
        left: zoom_offset_px + "px"
    });
}

function waterfall_init() {
    init_canvas_container();
    resize_canvases();
    scale_setup();
    mkzoomlevels();
    waterfall_setup_done = 1;
}

function waterfall_add(data) {
    if (!waterfall_setup_done) return;
    var w = fft_size;

    // measure waterfall min/max levels, if necessary
    Waterfall.measureRange(data);

    // create new canvas if the current one is full (or there isn't one)
    if (canvas_actual_line <= 0) add_canvas();

    // add line to waterfall image
    var oneline_image = canvas_context.createImageData(w, 1);
    Waterfall.drawLine(oneline_image.data, data);

    // draw image
    canvas_context.putImageData(oneline_image, 0, --canvas_actual_line);
    shift_canvases();
}

function waterfall_clear() {
    //delete all canvases
    while (canvases.length) {
        var x = canvases.shift();
        x.parentNode.removeChild(x);
    }
    canvas_actual_line = -1;
}

function openwebrx_resize() {
    resize_canvases();
    resize_scale();
}

function initProgressBars() {
    $(".openwebrx-progressbar").each(function(){
        var bar = $(this).progressbar();
        if ('setSampleRate' in bar) {
            bar.setSampleRate(audioEngine.getSampleRate());
        }
    })
}

function audioReporter(stats) {
    if (typeof(stats.buffersize) !== 'undefined') {
         $('#openwebrx-bar-audio-buffer').progressbar().setBuffersize(stats.buffersize);
    }

    if (typeof(stats.audioByteRate) !== 'undefined') {
        $('#openwebrx-bar-audio-speed').progressbar().setSpeed(stats.audioByteRate * 8);
    }

    if (typeof(stats.audioRate) !== 'undefined') {
        $('#openwebrx-bar-audio-output').progressbar().setAudioRate(stats.audioRate);
    }
}

function openwebrx_init() {
    // Name used by map links to tune receiver
    frames.name = 'openwebrx-rx';

    audioEngine = new AudioEngine(audio_buffer_maximal_length_sec, audioReporter);
    var $overlay = $('#openwebrx-autoplay-overlay');
    $overlay.on('click', function(){
        audioEngine.resume();
    });
    audioEngine.onStart(onAudioStart);
    if (!audioEngine.isAllowed()) {
        $('body').append($overlay);
        $overlay.show();
    }
    fft_codec = new ImaAdpcmCodec();
    initProgressBars();
    open_websocket();
    secondary_demod_init();
    digimodes_init();
    initSpectrum();
    initPanels();
    $('#openwebrx-panel-receiver').demodulatorPanel();
    window.addEventListener('resize', openwebrx_resize);
    bookmarks = new BookmarkBar();
    initSliders();

    // Initialize waterfall colors
    UI.setWfTheme('default');

    // Create bookmark scanner
    scanner = new Scanner(bookmarks, 1000);

    // Create bandplan ribbon display
    bandplan = new Bandplan(document.getElementById('openwebrx-bandplan-canvas'));

    // Create and run clock
    clock = new Clock($('#openwebrx-clock-utc'));
}

function initSliders() {
    $('#openwebrx-panel-receiver').on('wheel', 'input[type=range]', function(ev){
        var $slider = $(this);
        if (!$slider.attr('step') || $slider.attr('disabled')) return;
        var val = Number($slider.val());
        var step = Number($slider.attr('step'));
        if (ev.originalEvent.deltaY > 0) {
            step *= -1;
        }
        $slider.val(val + step);
        $slider.trigger('change');
    });

    // Enable continuous waterfall color adjustment by pressing the
    // right mouse button on AUTO
    $('#openwebrx-waterfall-colors-auto').on('contextmenu', function() {
        Waterfall.toggleContinuousRange();
        return false;
    });

    // Enable scanner by pressing the right mouse button on SQUELCH
    $('.openwebrx-squelch-auto').on('contextmenu', function() {
        UI.toggleScanner();
        return false;
    });
}

function digimodes_init() {
    // initialze DMR timeslot muting
    $('.openwebrx-dmr-timeslot-panel').click(function (e) {
        $(e.currentTarget).toggleClass("muted");
        update_dmr_timeslot_filtering();
    // don't mute when the location icon is clicked
    }).find('.location').click(function(e) {
        e.stopPropagation();
    });

    $('.openwebrx-meta-panel').metaPanel();
}

function update_dmr_timeslot_filtering() {
    var filter = $('.openwebrx-dmr-timeslot-panel').map(function (index, el) {
        return (!$(el).hasClass("muted")) << index;
    }).toArray().reduce(function (acc, v) {
        return acc | v;
    }, 0);
    UI.getDemodulator().setDmrFilter(filter);
}

function hideOverlay() {
    var $overlay = $('#openwebrx-autoplay-overlay');
    $overlay.css('opacity', 0);
    $overlay.on('transitionend', function() {
        $overlay.hide();
    });
}

var rt = function (s, n) {
    return s.replace(/[a-zA-Z]/g, function (c) {
        return String.fromCharCode((c <= "Z" ? 90 : 122) >= (c = c.charCodeAt(0) + n) ? c : c - 26);
    });
};

// ========================================================
// =======================  PANELS  =======================
// ========================================================

function panel_displayed(el){
    return !(el.style && el.style.display && el.style.display === 'none') && !(el.movement && el.movement === 'collapse');
}

function toggle_panel(what, on) {
    var item = $('#' + what)[0];
    if (!item) return;
    var displayed = panel_displayed(item);
    if (typeof on !== "undefined" && displayed === on) {
        return;
    }
    if (displayed) {
        item.movement = 'collapse';
        item.style.transform = "perspective(600px) rotateX(90deg)";
        item.style.transitionProperty = 'transform';
    } else {
        item.movement = 'expand';
        item.style.display = null;
        setTimeout(function(){
            item.style.transitionProperty = 'transform';
            item.style.transform = 'perspective(600px) rotateX(0deg)';
        }, 20);
    }
    item.style.transitionDuration = "600ms";
    item.style.transitionDelay = "0ms";
}

function first_show_panel(panel) {
    panel.style.transitionDuration = 0;
    panel.style.transitionDelay = 0;
    var rotx = (Math.random() > 0.5) ? -90 : 90;
    var roty = 0;
    if (Math.random() > 0.5) {
        var rottemp = rotx;
        rotx = roty;
        roty = rottemp;
    }
    if (rotx !== 0 && Math.random() > 0.5) rotx = 270;
    panel.style.transform = "perspective(600px) rotateX(%1deg) rotateY(%2deg)"
        .replace("%1", rotx.toString()).replace("%2", roty.toString());
    window.setTimeout(function () {
        panel.style.transitionDuration = "600ms";
        panel.style.transitionDelay = (Math.floor(Math.random() * 500)).toString() + "ms";
        panel.style.transform = "perspective(600px) rotateX(0deg) rotateY(0deg)";
    }, 1);
}

function initPanels() {
    $('#openwebrx-panels-container').find('.openwebrx-panel').each(function(){
        var el = this;
        el.openwebrxPanelTransparent = (!!el.dataset.panelTransparent);
        el.addEventListener('transitionend', function(ev){
            if (ev.target !== el) return;
            el.style.transitionDuration = null;
            el.style.transitionDelay = null;
            el.style.transitionProperty = null;
            if (el.movement && el.movement === 'collapse') {
                el.style.display = 'none';
            }
            delete el.movement;
        });
        if (panel_displayed(el)) first_show_panel(el);
    });

    // Apply nano-scroller to all panels that have 'nano' class
    $('.nano').nanoScroller();
}

function initSpectrum() {
    var canvas = document.getElementById('openwebrx-spectrum-canvas');

    // Assume spectrum display behaving like the waterfall
    canvas.addEventListener("mousedown", canvas_mousedown, false);
    canvas.addEventListener("mousemove", canvas_mousemove, false);
    canvas.addEventListener("mouseup", canvas_mouseup, false);
    canvas.addEventListener("wheel", canvas_mousewheel, false);
    canvas.addEventListener("touchmove", process_touch, false);
    canvas.addEventListener("touchend", process_touch, false);
    canvas.addEventListener("touchstart", process_touch, false);

    // Create spectrum display
    spectrum = new Spectrum(canvas, 150);
}

/*
  _____  _       _                     _
 |  __ \(_)     (_)                   | |
 | |  | |_  __ _ _ _ __ ___   ___   __| | ___  ___
 | |  | | |/ _` | | '_ ` _ \ / _ \ / _` |/ _ \/ __|
 | |__| | | (_| | | | | | | | (_) | (_| |  __/\__ \
 |_____/|_|\__, |_|_| |_| |_|\___/ \__,_|\___||___/
            __/ |
           |___/
*/

var secondary_demod_fft_offset_db = 18; //need to calculate that later
var secondary_demod_canvases_initialized = false;
var secondary_demod_channel_freq = 1000;
var secondary_demod_waiting_for_set = false;
var secondary_demod_low_cut;
var secondary_demod_high_cut;
var secondary_demod_mousedown = false;
var secondary_demod_canvas_width;
var secondary_demod_canvas_left;
var secondary_demod_canvas_container;
var secondary_demod_current_canvas_actual_line;
var secondary_demod_current_canvas_context;
var secondary_demod_current_canvas_index;
var secondary_demod_canvases;
var secondary_bw = 31.25;
var if_samp_rate;

function secondary_demod_create_canvas() {
    var new_canvas = document.createElement("canvas");
    new_canvas.width = secondary_fft_size;
    new_canvas.height = $(secondary_demod_canvas_container).height();
    new_canvas.style.width = $(secondary_demod_canvas_container).width() + "px";
    new_canvas.style.height = $(secondary_demod_canvas_container).height() + "px";
    secondary_demod_current_canvas_actual_line = new_canvas.height - 1;
    $(secondary_demod_canvas_container).children().last().before(new_canvas);
    return new_canvas;
}

function secondary_demod_remove_canvases() {
    $(secondary_demod_canvas_container).children("canvas").remove();
}

function secondary_demod_init_canvases() {
    secondary_demod_remove_canvases();
    secondary_demod_canvases = [];
    secondary_demod_canvases.push(secondary_demod_create_canvas());
    secondary_demod_canvases.push(secondary_demod_create_canvas());
    secondary_demod_canvases[0].openwebrx_top = -$(secondary_demod_canvas_container).height();
    secondary_demod_canvases[1].openwebrx_top = 0;
    secondary_demod_canvases_update_top();
    secondary_demod_current_canvas_context = secondary_demod_canvases[0].getContext("2d");
    secondary_demod_current_canvas_actual_line = $(secondary_demod_canvas_container).height() - 1;
    secondary_demod_current_canvas_index = 0;
    secondary_demod_canvases_initialized = true;
    mkscale(); //so that the secondary waterfall zoom level will be initialized
}

function secondary_demod_canvases_update_top() {
    for (var i = 0; i < 2; i++) {
        secondary_demod_canvases[i].style.transform = 'translate(0, ' + secondary_demod_canvases[i].openwebrx_top + 'px)';
    }
}

function secondary_demod_swap_canvases() {
    secondary_demod_canvases[0 + !secondary_demod_current_canvas_index].openwebrx_top -= $(secondary_demod_canvas_container).height() * 2;
    secondary_demod_current_canvas_index = 0 + !secondary_demod_current_canvas_index;
    secondary_demod_current_canvas_context = secondary_demod_canvases[secondary_demod_current_canvas_index].getContext("2d");
    secondary_demod_current_canvas_actual_line = $(secondary_demod_canvas_container).height() - 1;
}

function secondary_demod_init() {
    secondary_demod_canvas_container = $("#openwebrx-digimode-canvas-container")[0];
    $(secondary_demod_canvas_container)
        .mousemove(secondary_demod_canvas_container_mousemove)
        .mouseup(secondary_demod_canvas_container_mouseup)
        .mousedown(secondary_demod_canvas_container_mousedown)
        .mouseenter(secondary_demod_canvas_container_mousein)
        .mouseleave(secondary_demod_canvas_container_mouseleave);
    ['wsjt', 'packet', 'pocsag', 'page', 'sstv', 'fax', 'ism', 'hfdl', 'adsb', 'dsc', 'cwskimmer'].forEach(function(id){
        $('#openwebrx-panel-' + id + '-message')[id + 'MessagePanel']();
    })
    $('#openwebrx-panel-js8-message').js8();
}

function secondary_demod_push_data(x) {
    x = Array.from(x).filter(function (y) {
        var c = y.charCodeAt(0);
        return (c === 10 || (c >= 32 && c <= 126));
    }).map(function (y) {
        if (y === "&") return "&amp;";
        if (y === "<") return "&lt;";
        if (y === ">") return "&gt;";
        if (y === " ") return "&nbsp;";
        if (y === "\n") return "<br />";
        return y;
    }).join("");

    $("#openwebrx-cursor-blink").before(x);

    var nano = $('#openwebrx-digimode-content');
    nano.nanoScroller();
    nano.nanoScroller({scroll: 'bottom'});
}

function secondary_demod_waterfall_add(data) {
    var w = secondary_fft_size;

    // add line to waterfall image
    var oneline_image = secondary_demod_current_canvas_context.createImageData(w, 1);
    Waterfall.drawLine(oneline_image.data, data, secondary_demod_fft_offset_db);

    // draw image
    secondary_demod_current_canvas_context.putImageData(oneline_image, 0, secondary_demod_current_canvas_actual_line--);
    secondary_demod_canvases.map(function (x) { x.openwebrx_top += 1; });

    secondary_demod_canvases_update_top();
    if (secondary_demod_current_canvas_actual_line < 0) secondary_demod_swap_canvases();
}

function secondary_demod_update_marker() {
    var width = Math.max((secondary_bw / if_samp_rate) * secondary_demod_canvas_width, 5);
    var center_at = ((secondary_demod_channel_freq - secondary_demod_low_cut) / if_samp_rate) * secondary_demod_canvas_width;
    var left = center_at - width / 2;
    $("#openwebrx-digimode-select-channel").width(width).css("left", left + "px")
}

function secondary_demod_update_channel_freq_from_event(evt) {
    if (typeof evt !== "undefined") {
        var relativeX = (evt.offsetX) ? evt.offsetX : evt.layerX;
        secondary_demod_channel_freq = secondary_demod_low_cut +
            (relativeX / $(secondary_demod_canvas_container).width()) * (secondary_demod_high_cut - secondary_demod_low_cut);
    }
    if (!secondary_demod_waiting_for_set) {
        secondary_demod_waiting_for_set = true;
        window.setTimeout(function () {
                UI.getDemodulator().set_secondary_offset_freq(Math.floor(secondary_demod_channel_freq));
                secondary_demod_waiting_for_set = false;
            },
            50
        )
        ;
    }
    secondary_demod_update_marker();
}

function secondary_demod_canvas_container_mousein() {
    $("#openwebrx-digimode-select-channel").css("opacity", "0.7"); //.css("border-width", "1px");
}

function secondary_demod_canvas_container_mouseleave() {
    $("#openwebrx-digimode-select-channel").css("opacity", "0");
}

function secondary_demod_canvas_container_mousemove(evt) {
    if (secondary_demod_mousedown) secondary_demod_update_channel_freq_from_event(evt);
}

function secondary_demod_canvas_container_mousedown(evt) {
    if (evt.which === 1) secondary_demod_mousedown = true;
}

function secondary_demod_canvas_container_mouseup(evt) {
    if (evt.which === 1) secondary_demod_mousedown = false;
    secondary_demod_update_channel_freq_from_event(evt);
}


function secondary_demod_waterfall_set_zoom(low_cut, high_cut) {
    if (!secondary_demod_canvases_initialized) return;
    secondary_demod_low_cut = low_cut;
    secondary_demod_high_cut = high_cut;
    var shown_bw = high_cut - low_cut;
    secondary_demod_canvas_width = $(secondary_demod_canvas_container).width() * (if_samp_rate) / shown_bw;
    secondary_demod_canvas_left = (-secondary_demod_canvas_width / 2) - (low_cut / if_samp_rate) * secondary_demod_canvas_width;
    secondary_demod_canvases.map(function (x) {
        $(x).css({
            left: secondary_demod_canvas_left + "px",
            width: secondary_demod_canvas_width + "px"
        });
    });

    // Make sure secondary demod frequency is within bandpass
    var f = secondary_demod_channel_freq;
    if ((f < low_cut) || (f > high_cut)) {
        if ((-f >= low_cut) && (-f <= high_cut)) f = -f;
        else f = Math.floor((low_cut + high_cut) / 2);
        secondary_demod_channel_freq = f;
    }

    secondary_demod_update_channel_freq_from_event();
}

function sdr_profile_changed() {
    var value = $('#openwebrx-sdr-profiles-listbox').val();
    var key = UI.getDemodulatorPanel().getMagicKey();
    ws.send(JSON.stringify({
        "type": "selectprofile", "params": { "profile": value, "key": key }
    }));
}

function tuning_step_changed() {
    tuning_step = parseInt($('#openwebrx-tuning-step-listbox').val());
}

function tuning_step_reset() {
    $('#openwebrx-tuning-step-listbox').val(tuning_step_default);
    tuning_step = tuning_step_default;
}
