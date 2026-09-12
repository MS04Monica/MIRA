// IP Webcam API Host Address
const IP_WEBCAM_HOST = "http://192.0.0.4:8080";

// Blynk Cloud Configuration
const BLYNK_AUTH = "U1p3Lkg6PKWsjbTDQfMCefZ0Nn4B5Cbg";
const BLYNK_UPDATE_URL = `https://blynk.cloud/external/api/update?token=${BLYNK_AUTH}`;

let activeDirectionPin = null;

// Direct HTTP REST Call to update Blynk Virtual Pins
function setBlynkPin(vPin, state) {
  fetch(`${BLYNK_UPDATE_URL}&${vPin}=${state}`).catch((err) =>
    console.error("[Blynk Drive Error]:", err),
  );
}

// Camera Switch Logic
function switchCameraLens(lensId) {
  fetch(`${IP_WEBCAM_HOST}/settings/ffc?set=${lensId}`, { mode: "no-cors" })
    .then(() => {
      document.getElementById("cam-lens-mode").innerText =
        lensId === 1 ? "LENS: FRONT CAM" : "LENS: BACK CAM";
      document
        .getElementById("btn-back")
        .classList.toggle("active", lensId === 0);
      document
        .getElementById("btn-front")
        .classList.toggle("active", lensId === 1);
      setTimeout(reconnectStream, 500);
    })
    .catch((err) => console.error("Error switching lens:", err));
}

function reconnectStream() {
  const img = document.getElementById("mobile-camera-feed");
  img.src = `${IP_WEBCAM_HOST}/video?` + new Date().getTime();
}

// Teleoperation Handler (Integrated with ESP8266 Virtual Pins V1-V4)
function sendDrive(cmd) {
  const pinMap = { W: "V1", S: "V2", A: "V3", D: "V4" };
  const btnMap = { W: "k-w", A: "k-a", S: "k-s", D: "k-d", STOP: "k-space" };

  if (cmd === "STOP") {
    ["V1", "V2", "V3", "V4"].forEach((pin) => setBlynkPin(pin, 0));
    activeDirectionPin = null;

    Object.values(btnMap).forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.classList.remove("active");
    });
  } else if (pinMap[cmd]) {
    const targetPin = pinMap[cmd];
    if (activeDirectionPin !== targetPin) {
      sendDrive("STOP");
      activeDirectionPin = targetPin;
      setBlynkPin(targetPin, 1);

      const el = document.getElementById(btnMap[cmd]);
      if (el) el.classList.add("active");
    }
  }
}

// Keyboard Binds
window.addEventListener("keydown", (e) => {
  if (e.repeat) return;
  const k = e.key.toUpperCase();
  if (["W", "A", "S", "D"].includes(k)) sendDrive(k);
  if (e.key === " ") sendDrive("STOP");
});

window.addEventListener("keyup", (e) => {
  const k = e.key.toUpperCase();
  if (["W", "A", "S", "D"].includes(k)) sendDrive("STOP");
});

// Chart Initialization
const ctx = document.getElementById("gasTrendChart").getContext("2d");
const tempChart = new Chart(ctx, {
  type: "line",
  data: {
    labels: ["--:--", "--:--", "--:--", "--:--", "--:--", "NOW"],
    datasets: [
      {
        label: "Temperature °C",
        data: [0, 0, 0, 0, 0, 0],
        borderColor: "#ff9f43",
        backgroundColor: "rgba(255, 159, 67, 0.12)",
        fill: true,
        tension: 0.3,
        borderWidth: 2,
      },
    ],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: {
        ticks: { color: "#a0aab8" },
        grid: { color: "rgba(255,255,255,0.05)" },
      },
      y: {
        ticks: { color: "#a0aab8" },
        grid: { color: "rgba(255,255,255,0.05)" },
        beginAtZero: true,
      },
    },
  },
});

// REAL-TIME TELEMETRY POLLING (Mapped strictly to your C++ pin structure)
function pollBlynkTelemetry() {
  // Check hardware online status
  fetch(
    `https://blynk.cloud/external/api/isHardwareConnected?token=${BLYNK_AUTH}`,
  )
    .then((res) => res.json())
    .then((isConnected) => {
      if (!isConnected) {
        [
          "val-humidity",
          "val-temp",
          "val-gas",
          "val-vibration",
          "val-proximity",
        ].forEach((id) => {
          const el = document.getElementById(id);
          if (el) {
            el.innerText = "OFFLINE";
            el.style.color = "var(--text-muted)";
          }
        });
        return;
      }

      // Fetch exact V5, V6, V7, V8, V9 from Blynk Cloud
      fetch(
        `https://blynk.cloud/external/api/get?token=${BLYNK_AUTH}&V5&V6&V7&V8&V9`,
      )
        .then((response) => response.json())
        .then((data) => {
          // 1. Humidity (V5)
          if (data.V5 !== undefined) {
            document.getElementById("val-humidity").innerText = `${data.V5}%`;
            document.getElementById("val-humidity").style.color = "#00d2ff";
          }

          // 2. Temperature (V6)
          if (data.V6 !== undefined) {
            const tempVal = parseFloat(data.V6);
            document.getElementById("val-temp").innerText = `${tempVal} °C`;
            document.getElementById("val-temp").style.color = "#ff9f43";

            // Update Chart
            const nowTime = new Date().toLocaleTimeString().split(" ")[0];
            tempChart.data.labels.shift();
            tempChart.data.labels.push(nowTime);
            tempChart.data.datasets[0].data.shift();
            tempChart.data.datasets[0].data.push(tempVal);
            tempChart.update("none");
          }

          // 3. Gas Alert (V7)
          if (data.V7 !== undefined) {
            const gasElem = document.getElementById("val-gas");
            const isGasDetected = String(data.V7).includes("GAS DETECTED");
            gasElem.innerText = isGasDetected ? "GAS DETECTED" : "NORMAL";
            gasElem.style.color = isGasDetected
              ? "var(--alert-red)"
              : "var(--safe-green)";
          }

          // 4. Vibration Alert (V8)
          if (data.V8 !== undefined) {
            const vibElem = document.getElementById("val-vibration");
            const isVibDetected = String(data.V8).includes(
              "VIBRATION DETECTED",
            );
            vibElem.innerText = isVibDetected ? "VIBRATION DETECTED" : "NORMAL";
            vibElem.style.color = isVibDetected
              ? "var(--alert-red)"
              : "var(--safe-green)";
          }

          // 5. Object Detection Alert (V9)
          if (data.V9 !== undefined) {
            const objElem = document.getElementById("val-proximity");
            const isObjDetected = String(data.V9).includes("OBJECT DETECTED");
            objElem.innerText = isObjDetected ? "OBJECT DETECTED" : "NORMAL";
            objElem.style.color = isObjDetected
              ? "var(--alert-red)"
              : "var(--safe-green)";
          }
        });
    })
    .catch((err) => console.error("[Blynk Error]:", err));
}

// Poll Blynk Cloud every 1.5 seconds
setInterval(pollBlynkTelemetry, 1500);
pollBlynkTelemetry();
