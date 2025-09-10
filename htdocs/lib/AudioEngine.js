// this controls if the new AudioWorklet API should be used if available.
// the engine will still fall back to the ScriptProcessorNode if this is set to true but not available in the browser.
var useAudioWorklets = true;

function AudioEngine(maxBufferLength, audioReporter) {
    this.audioReporter = audioReporter;
    this.initStats();
    this.resetStats();

    this.onStartCallbacks = [];

    this.started = false;
    this.audioContext = this.buildAudioContext();
    if (!this.audioContext) {
        return;
    }

    var me = this;
    this.audioContext.onstatechange = function() {
        if (me.audioContext.state !== 'running') return;
        me._start();
    }

    this.audioCodec = new ImaAdpcmCodec();
    this.compression = 'none';

    this.setupResampling();
    this.resampler = new Interpolator(this.resamplingFactor);
    this.hdResampler = new Interpolator(this.hdResamplingFactor);

    this.maxBufferSize = maxBufferLength * this.getSampleRate();

    this.recorder = new AudioRecorder(this.getOutputRate(), 128);
    this.hdRecorder = new AudioRecorder(this.getHdOutputRate(), 128);
    this.recording = false;
    this.lastHd = false;
}

AudioEngine.prototype.buildAudioContext = function() {
    var ctxClass = window.AudioContext || window.webkitAudioContext;
    if (!ctxClass) {
        return;
    }

    // known good sample rates
    var goodRates = [48000, 44100, 96000]

    // let the browser chose the sample rate, if it is good, use it
    var ctx = new ctxClass({latencyHint: 'playback'});
    if (goodRates.indexOf(ctx.sampleRate) >= 0) {
        return ctx;
    }

    // if that didn't work, try if any of the good rates work
    if (goodRates.some(function(sr) {
        try {
            ctx = new ctxClass({sampleRate: sr, latencyHint: 'playback'});
            return true;
        } catch (e) {
            return false;
        }
    }, this)) {
        return ctx;
    }

    // fallback: let the browser decide
    // this may cause playback problems down the line
    return new ctxClass({latencyHint: 'playback'});
}

AudioEngine.prototype.resume = function(){
    this.audioContext.resume();
}

AudioEngine.prototype._start = function() {
    var me = this;

    // if failed to find a valid resampling factor...
    if (me.resamplingFactor === 0) {
         return;
    }

    // been started before?
    if (me.started) {
        return;
    }

    // are we allowed to play audio?
    if (!me.isAllowed()) {
        return;
    }
    me.started = true;

    var runCallbacks = function(workletType) {
        var callbacks = me.onStartCallbacks;
        me.onStartCallbacks = false;
        callbacks.forEach(function(c) { c(workletType); });
    };

    me.gainNode = me.audioContext.createGain();
    me.gainNode.connect(me.audioContext.destination);

    if (useAudioWorklets && me.audioContext.audioWorklet) {
        me.audioContext.audioWorklet.addModule('static/lib/AudioProcessor.js').then(function(){
            me.audioNode = new AudioWorkletNode(me.audioContext, 'openwebrx-audio-processor', {
                numberOfInputs: 0,
                numberOfOutputs: 1,
                outputChannelCount: [2],
                processorOptions: {
                    maxBufferSize: me.maxBufferSize
                }
            });
            me.audioNode.connect(me.gainNode);
            me.audioNode.port.addEventListener('message', function(m){
                var json = JSON.parse(m.data);
                if (typeof(json.buffersize) !== 'undefined') {
                    me.audioReporter({
                        buffersize: json.buffersize
                    });
                }
                if (typeof(json.samplesProcessed) !== 'undefined') {
                    me.audioSamples.add(json.samplesProcessed);
                }
            });
            me.audioNode.port.start();
            runCallbacks('AudioWorklet');
        });
    } else {
        me.audioBuffers = [];

        if (!AudioBuffer.prototype.copyToChannel) { //Chrome 36 does not have it, Firefox does
            AudioBuffer.prototype.copyToChannel = function (input, channel) //input is Float32Array
            {
                var cd = this.getChannelData(channel);
                for (var i = 0; i < input.length; i++) cd[i] = input[i];
            }
        }

        var bufferSize;
        if (me.audioContext.sampleRate < 44100 * 2)
            bufferSize = 4096;
        else if (me.audioContext.sampleRate >= 44100 * 2 && me.audioContext.sampleRate < 44100 * 4)
            bufferSize = 4096 * 2;
        else if (me.audioContext.sampleRate > 44100 * 4)
            bufferSize = 4096 * 4;


        function audio_onprocess(e) {
            var total = 0;
            var out = new Float32Array(bufferSize);
            while (me.audioBuffers.length) {
                var b = me.audioBuffers.shift();
                // not enough space to fit all data, so splice and put back in the queue
                if (total + b.length > bufferSize) {
                    var spaceLeft  = bufferSize - total;
                    var tokeep = b.subarray(0, spaceLeft);
                    out.set(tokeep, total);
                    var tobuffer = b.subarray(spaceLeft, b.length);
                    me.audioBuffers.unshift(tobuffer);
                    total += spaceLeft;
                    break;
                } else {
                    out.set(b, total);
                    total += b.length;
                }
            }

            e.outputBuffer.copyToChannel(out, 0);
            e.outputBuffer.copyToChannel(out, 1);
            me.audioSamples.add(total);

        }

        //on Chrome v36, createJavaScriptNode has been replaced by createScriptProcessor
        var method = 'createScriptProcessor';
        if (me.audioContext.createJavaScriptNode) {
            method = 'createJavaScriptNode';
        }
        me.audioNode = me.audioContext[method](bufferSize, 0, 2);
        me.audioNode.onaudioprocess = audio_onprocess;
        me.audioNode.connect(me.gainNode);
        runCallbacks('ScriptProcessorNode')
    }

    setInterval(me.reportStats.bind(me), 1000);
};

AudioEngine.prototype.onStart = function(callback) {
    if (this.onStartCallbacks) {
        this.onStartCallbacks.push(callback);
    } else {
        callback();
    }
};

AudioEngine.prototype.isAllowed = function() {
    return this.audioContext.state === 'running';
};

AudioEngine.prototype.isStarted = function() {
    return this.started;
};

AudioEngine.prototype.reportStats = function() {
    if (this.audioNode.port) {
        this.audioNode.port.postMessage(JSON.stringify({cmd:'getStats'}));
    } else {
        this.audioReporter({
            buffersize: this.getBuffersize()
        });
    }
};

AudioEngine.prototype.initStats = function() {
    var me = this;
    var buildReporter = function(key) {
        return function(v){
            var report = {};
            report[key] = v;
            me.audioReporter(report);
        }

    };

    this.audioBytes = new Measurement();
    this.audioBytes.report(10000, 1000, buildReporter('audioByteRate'));

    this.audioSamples = new Measurement();
    this.audioSamples.report(10000, 1000, buildReporter('audioRate'));
};

AudioEngine.prototype.resetStats = function() {
    this.audioBytes.reset();
    this.audioSamples.reset();
};

AudioEngine.prototype.setupResampling = function() { //both at the server and the client
    var targetRate = this.audioContext.sampleRate;
    var audio_params = this.findRate(8000, 12000);
    if (!audio_params) {
        this.resamplingFactor = 0;
        this.outputRate = 0;
        divlog('Your audio card sampling rate (' + targetRate + ') is not supported.<br />Please change your operating system default settings in order to fix this.', 1);
    } else {
        this.resamplingFactor = audio_params.resamplingFactor;
        this.outputRate = audio_params.outputRate;
    }

    var hd_audio_params = this.findRate(36000, 48000);
    if (!hd_audio_params) {
        this.hdResamplingFactor = 0;
        this.hdOutputRate = 0;
        divlog('Your audio card sampling rate (' + targetRate + ') is not supported for HD audio<br />Please change your operating system default settings in order to fix this.', 1);
    } else {
        this.hdResamplingFactor = hd_audio_params.resamplingFactor;
        this.hdOutputRate = hd_audio_params.outputRate;
    }
};

AudioEngine.prototype.findRate = function(low, high) {
    var targetRate = this.audioContext.sampleRate;
    var i = 1;
    while (true) {
        var audio_server_output_rate = Math.floor(targetRate / i);
        if (audio_server_output_rate < low) {
            return;
        } else if (audio_server_output_rate >= low && audio_server_output_rate <= high) {
            return {
                resamplingFactor: i,
                outputRate: audio_server_output_rate
            }
        }
        i++;
    };
}

AudioEngine.prototype.getOutputRate = function() {
    return this.outputRate;
};

AudioEngine.prototype.getHdOutputRate = function() {
    return this.hdOutputRate;
}

AudioEngine.prototype.getSampleRate = function() {
    return this.audioContext.sampleRate;
};

AudioEngine.prototype.processAudio = function(data, resampler, recorder) {
    // audio must be initialized
    if (!this.audioNode) return;

    // make sure that data is an array of channels
    if (!Array.isArray(data)) data = [ data ];

    var buffer = [];
    for (var j = 0 ; j < data.length ; j++) {
        // allocate space
        this.audioBytes[j].add(data[j].byteLength);
        // decompress
        if (this.compression === "adpcm") {
            buffer[j] = this.audioCodec.decodeWithSync(new Uint8Array(data[j]));
        } else {
            buffer[j] = new Int16Array(data[j]);
        }
    }

    // record to MP3
    if (this.recording) recorder.record(buffer);

    // resample
    for (var j = 0 ; j < data.length ; j++) {
        buffer[j] = resampler.process(buffer[j]);
    }

    if (this.audioNode.port) {
        // AudioWorklets supported
        this.audioNode.port.postMessage(buffer);
    } else if (this.getBuffersize() + buffer[0].length <= this.maxBufferSize) {
        // silently drop excess samples
        this.audioBuffers.push(buffer);
    }
}

AudioEngine.prototype.pushAudio = function(data) {
    this.processAudio(data, this.resampler, this.recorder);
    this.lastHd = false;
};

AudioEngine.prototype.pushHdAudio = function(data) {
    this.processAudio(data, this.hdResampler, this.hdRecorder);
    this.lastHd = true;
}

AudioEngine.prototype.pushHdStereo = function(data) {
    this.processAudio(data.filter((e, i) => { return !(i&1); }), this.hdResampler, this.hdRecorder);
    this.lastHd = true;
}

AudioEngine.prototype.setCompression = function(compression) {
    this.compression = compression;
};

AudioEngine.prototype.setVolume = function(volume) {
    this.gainNode.gain.value = volume;
};

AudioEngine.prototype.getBuffersize = function() {
    // only available when using ScriptProcessorNode
    if (!this.audioBuffers) return 0;
    return this.audioBuffers.map(function(b){ return b.length; }).reduce(function(a, b){ return a + b; }, 0);
};

AudioEngine.prototype.startRecording = function() {
    if (!this.recording) {
        var date = new Date(Date.now()).toISOString().slice(2,19)
            .replaceAll('-','').replaceAll(':','').replaceAll('T','-');
        var freq = Math.round(UI.getFrequency() / 1000);
        this.mp3fileName = "REC-" + date + '-' + freq + ".mp3";
        this.recording = true;
    }
};

AudioEngine.prototype.stopRecording = function() {
    if (this.recording) {
        this.recording = false;

        // Save last updated recording
        if (this.lastHd) {
            this.hdRecorder.saveRecording(this.mp3fileName);
        } else {
            this.recorder.saveRecording(this.mp3fileName);
        }

        // Clear and stop all recorders
        this.hdRecorder.stopRecording();
        this.recorder.stopRecording();
    }
};

function AudioRecorder(sampleRate, kbps) {
    // Mono (1 channel), with given sample rate and bitrate
    this.mp3encoder = new lamejs.Mp3Encoder(1, sampleRate, kbps);
    this.blockSize  = 1152; // better be a multiple of 576
    this.mp3Data    = [];
}

AudioRecorder.prototype.record = function(samples) {
    for (var i = 0; i < samples.length; i += this.blockSize) {
        var chunk  = samples.subarray(i, i + this.blockSize);
        var mp3buf = this.mp3encoder.encodeBuffer(chunk);
        if (mp3buf.length > 0) this.mp3Data.push(mp3buf);
    }
};

AudioRecorder.prototype.stopRecording = function() {
    this.mp3encoder.flush();
    this.mp3Data = [];
}

AudioRecorder.prototype.saveRecording = function(name) {
    // finish writing mp3
    var mp3buf = this.mp3encoder.flush();
    if (mp3buf.length>0) this.mp3Data.push(new Int8Array(mp3buf));

    // Do not save unless we have data
    if (this.mp3Data.length==0) return false;

    var blob = new Blob(this.mp3Data, {type: "audio/mp3"});

    var a = document.createElement("a");
    a.href = window.URL.createObjectURL(blob);
    a.style = "display: none";
    a.download = name;
    document.body.appendChild(a);
    a.click();

    setTimeout(function() {
        document.body.removeChild(a);
        window.URL.revokeObjectURL(a.href);
    }, 0);

    // Success
    return true;
};

function ImaAdpcmCodec() {
    this.reset();
}

ImaAdpcmCodec.prototype.reset = function() {
    this.stepIndex = 0;
    this.predictor = 0;
    this.step = 0;
    this.synchronized = 0;
    this.syncWord = "SYNC";
    this.syncCounter = 0;
    this.phase = 0;
    this.syncBuffer = new Uint8Array(4);
    this.syncBufferIndex = 0;
};

ImaAdpcmCodec.imaIndexTable = [ -1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8 ];

ImaAdpcmCodec.imaStepTable = [
                               7, 8, 9, 10, 11, 12, 13, 14, 16, 17,
                               19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
                               50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
                               130, 143, 157, 173, 190, 209, 230, 253, 279, 307,
                               337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
                               876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
                               2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358,
                               5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
                               15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767
                             ];

ImaAdpcmCodec.prototype.decode = function(data) {
    var output = new Int16Array(data.length * 2);
    for (var i = 0; i < data.length; i++) {
        output[i * 2] = this.decodeNibble(data[i] & 0x0F);
        output[i * 2 + 1] = this.decodeNibble((data[i] >> 4) & 0x0F);
    }
    return output;
};

ImaAdpcmCodec.prototype.decodeWithSync = function(data) {
    var output = new Int16Array(data.length * 2);
    var oi = 0;
    for (var index = 0; index < data.length; index++) {
        switch (this.phase) {
            case 0:
                // search for sync word
                if (data[index] !== this.syncWord.charCodeAt(this.synchronized++)) {
                    // reset if data is unexpected
                    this.synchronized = 0;
                }
                // if sync word has been found pass on to next phase
                if (this.synchronized === 4) {
                    this.syncBufferIndex = 0;
                    this.phase = 1;
                }
                break;
            case 1:
                // read codec runtime data from stream
                this.syncBuffer[this.syncBufferIndex++] = data[index];
                // if data is complete, apply and pass on to next phase
                if (this.syncBufferIndex === 4) {
                    var syncData = new Int16Array(this.syncBuffer.buffer);
                    this.stepIndex = syncData[0];
                    this.predictor = syncData[1];
                    this.syncCounter = 1000;
                    this.phase = 2;
                }
                break;
            case 2:
                // decode actual audio data
                output[oi++] = this.decodeNibble(data[index] & 0x0F);
                output[oi++] = this.decodeNibble(data[index] >> 4);
                // if the next sync keyword is due, reset and return to phase 0
                if (this.syncCounter-- === 0) {
                    this.synchronized = 0;
                    this.phase = 0;
                }
                break;
        }
    }
    return output.slice(0, oi);
};

ImaAdpcmCodec.prototype.decodeNibble = function(nibble) {
    this.stepIndex += ImaAdpcmCodec.imaIndexTable[nibble];
    this.stepIndex = Math.min(Math.max(this.stepIndex, 0), 88);

    var diff = this.step >> 3;
    if (nibble & 1) diff += this.step >> 2;
    if (nibble & 2) diff += this.step >> 1;
    if (nibble & 4) diff += this.step;
    if (nibble & 8) diff = -diff;

    this.predictor += diff;
    this.predictor = Math.min(Math.max(this.predictor, -32768), 32767);

    this.step = ImaAdpcmCodec.imaStepTable[this.stepIndex];

    return this.predictor;
};

function Interpolator(factor) {
    this.factor = factor;
    this.lowpass = new Lowpass(factor)
}

Interpolator.prototype.process = function(data) {
    var output = new Float32Array(data.length * this.factor);
    for (var i = 0; i < data.length; i++) {
        output[i * this.factor] = (data[i] + 0.5) / 32768;
    }
    return this.lowpass.process(output);
};

function Lowpass(interpolation) {
    this.interpolation = interpolation;
    var transitionBandwidth = 0.05;
    this.numtaps = Math.round(4 / transitionBandwidth);
    if (this.numtaps % 2 == 0) this.numtaps += 1;

    var cutoff = 1 / interpolation;
    this.coefficients = this.getCoefficients(cutoff / 2);

    this.delay = new Float32Array(this.numtaps);
    for (var i = 0; i < this.numtaps; i++){
        this.delay[i] = 0;
    }
    this.delayIndex = 0;
}

Lowpass.prototype.getCoefficients = function(cutoffRate) {
    var middle = Math.floor(this.numtaps / 2);
    // hamming window
    var window_function = function(r){
        var rate = 0.5 + r / 2;
        return 0.54 - 0.46 * Math.cos(2 * Math.PI * rate);
    }
    var output = [];
    output[middle] = 2 * Math.PI * cutoffRate * window_function(0);
    for (var i = 1; i <= middle; i++) {
        output[middle - i] = output[middle + i] = (Math.sin(2 * Math.PI * cutoffRate * i) / i) * window_function(i / middle);
    }
    return this.normalizeCoefficients(output);
};

Lowpass.prototype.normalizeCoefficients = function(input) {
    var sum = 0;
    var output = [];
    for (var i = 0; i < input.length; i++) {
        sum += input[i];
    }
    for (var i = 0; i < input.length; i++) {
        output[i] = input[i] / sum;
    }
    return output;
};

Lowpass.prototype.process = function(input) {
    output = new Float32Array(input.length);
    for (var oi = 0; oi < input.length; oi++) {
        this.delay[this.delayIndex] = input[oi];
        this.delayIndex = (this.delayIndex + 1) % this.numtaps;

        var acc = 0;
        var index = this.delayIndex;
        for (var i = 0; i < this.numtaps; ++i) {
            var index = index != 0 ? index - 1 : this.numtaps - 1;
            acc += this.delay[index] * this.coefficients[i];
            if (isNaN(acc)) debugger;
        }
        // gain by interpolation
        output[oi] = this.interpolation * acc;
    }
    return output;
};
