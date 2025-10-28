document.addEventListener('DOMContentLoaded', () => {
    const joystickLeft = nipplejs.create({
        zone: document.getElementById('joystick-left'),
        mode: 'static',
        position: { left: '50%', top: '50%' },
        color: 'white'
    });

    const joystickRight = nipplejs.create({
        zone: document.getElementById('joystick-right'),
        mode: 'static',
        position: { left: '50%', top: '50%' },
        color: 'white'
    });

    // Helper: send JSON command to Flask
    function sendCommand(command) {
        fetch('/joystick', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(command)
        }).catch(err => console.error('Send failed:', err));
    }

    // LEFT joystick → throttle (Y) + yaw (X)
joystickLeft.on('move', (evt, data) => {
    const t = -data.vector.y;  // invert so up = +1
    const y = data.vector.x;
    sendCommand({ throttle: t, yaw: y });
});

// RIGHT joystick → pitch (Y) + roll (X)
joystickRight.on('move', (evt, data) => {
    const p = -data.vector.y;  // invert so up = +1
    const r = data.vector.x;
    sendCommand({ pitch: p, roll: r });
});


    // Dummy telemetry updates
    setInterval(() => {
        const battery = Math.floor(Math.random() * 100);
        const altitude = (Math.random() * 10).toFixed(1);
        const speed = (Math.random() * 20).toFixed(1);

        document.getElementById('battery-level').textContent = `${battery}%`;
        document.getElementById('altitude').textContent = `${altitude}m`;
        document.getElementById('speed').textContent = `${speed}km/h`;
    }, 2000);

function sendCommand(command) {
    fetch('/joystick', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(command)
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'ok' && data.sent) {
            const throttle = data.sent.throttle.toFixed(0);
            document.getElementById('throttle-display').innerText = throttle;
        }
    })
    .catch(err => console.error('Send failed:', err));
}



const armButton = document.getElementById('arm-button');
const disarmButton = document.getElementById('disarm-button');
const armedStatus = document.getElementById('armed-status');

armButton.addEventListener('click', () => {
    fetch('/arm', { method: 'POST' })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'ok') {
            armedStatus.innerText = "ARMED";
            armedStatus.style.color = "green";
        }
    });
});

disarmButton.addEventListener('click', () => {
    fetch('/disarm', { method: 'POST' })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'ok') {
            armedStatus.innerText = "DISARMED";
            armedStatus.style.color = "red";
        }
    });
});

});
