window.addEventListener("DOMContentLoaded", function() {
    document.querySelectorAll("input.copy").forEach(function(e) {
        var copy = document.createElement("input");
        copy.type = "button";
        copy.className = "copy-button";
        copy.value = "Copy";
        e.parentNode.insertBefore(copy, e.nextSibling);
        var t;
        async function callback(evt) {
            evt.preventDefault();
            await navigator.clipboard.writeText(e.value);
            copy.value = "Copied!";
            t = setTimeout(function() {
                copy.value = "Copy";
            }, 2000);
        }
        e.addEventListener("click", callback);
        copy.addEventListener("click", callback);
    });
});
