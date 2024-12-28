window.addEventListener("DOMContentLoaded", async function() {
    function addConfetti() {
        var script = document.createElement("script");
        script.src = "https://cdn.jsdelivr.net/npm/canvas-confetti@1";
        script.addEventListener("load", function() {
            confetti({
                particleCount: 200,
                spread: 180,
                startVelocity: 60,
                origin: { y: 0.6 },
                gravity: 0.5,
                ticks: 300,
            });
        });
        document.head.appendChild(script);
    }
    var statusElement = document.querySelector(".status");
    var conclusionElement = document.querySelector(".conclusion");
    var loader = document.querySelector(".loader");
    var finalMessage = document.createElement("div");
    async function check() {
        var resp = await fetch("/status");
        var data = await resp.json();
        var status = data.status;
        statusElement.innerText = status;
        var conclusion = data.conclusion;
        conclusionElement.innerText = conclusion;
        if(status == "completed" && conclusion == "success") {
            finalMessage.className = "success";
            finalMessage.innerHTML = 'Congratulations, everything works!<br>You can go to the <a href="' + data.job_url + '" target="_blank">workflow page</a> to check the logs.<br>You can also revoke the token (go to the previous tab and click on <i>Delete</i>).';
            addConfetti();
        } else if(status != "in_progress" && status != "queued" && status != "requested" && status != "waiting" && status != "pending" && conclusion != "action_required" && conclusion != "neutral" && conclusion != "skipped") {
            finalMessage.className = "error";
            finalMessage.innerHTML = 'Oops, there was an unexpected error!<br>Go to the <a href="' + data.job_url + '" target="_blank">workflow page</a> to see what happened.';
        } else {
            return;
        }
        clearInterval(intv);
        loader.remove();
        document.body.appendChild(finalMessage);
    }
    var intv = setInterval(check, 5000);
    await check();
});
