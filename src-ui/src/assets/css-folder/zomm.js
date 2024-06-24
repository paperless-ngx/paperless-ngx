document.addEventListener("DOMContentLoaded", function() {
    var folderLeft = document.getElementById('folderLeft');
    var folderright = document.getElementById('folderrightt');
    var folderContainer = document.querySelector('.folder-container');
    var zoom = document.getElementById("zoomImg");
    var contextMenu = document.getElementById("contextMenu");
    var toggleButton = document.getElementById("toggleButton"); 
    
    var eventsEnabled = false;


    var amButton = document.getElementById("am");
    var subFolderContainer = document.querySelector('.sub-folder-container');

    amButton.addEventListener("click", function() {

        subFolderContainer.style.display = "block";

        contextMenu.style.display = "none";
    

        var inputInSubFolder = subFolderContainer.querySelector('input[type="text"]');
        if (inputInSubFolder) {
            inputInSubFolder.focus();
        }
    

        var allInputs = document.querySelectorAll('input');
        allInputs.forEach(function(input) {
            if (input !== inputInSubFolder) {
                input.blur();
            }
        });
    });
    document.getElementById('sss').addEventListener('click', function() {
        var contextMenu1 = document.querySelector('.sub-folder-container');
        contextMenu1.style.display = 'none'; 
    });

 
    folderLeft.addEventListener('click', function() {
        hideContextMenu();
    });


    folderLeft.addEventListener('contextmenu', function(event) {
        event.preventDefault();
        showContextMenu(event.clientX, event.clientY);
    });

  
    folderright.addEventListener('contextmenu', function(event) {
        event.preventDefault();
        showContextMenu(event.clientX, event.clientY);
    });

 
    document.addEventListener('mousedown', function(event) {
        var targetElement = event.target;

        var clickedInsideContextMenu = contextMenu.contains(targetElement);
        var clickedInsideFolderContainer = folderContainer.contains(targetElement);
        var clickedInsideAddFolder = targetElement.classList.contains('addfolder') || targetElement.closest('.addfolder');
        var clickedInsideAm = targetElement.id === 'am' || targetElement.closest('#am');

        if (!clickedInsideContextMenu && !clickedInsideAddFolder && !clickedInsideAm) {
            hideContextMenu();
        }

       
        if (clickedInsideAm) {
            event.preventDefault();
        }
    });

  
    toggleButton.addEventListener("click", function() {
        toggleEvents();
    });

    function showContextMenu(x, y) {
        contextMenu.style.display = "block";
        contextMenu.style.left = x + "px";
        contextMenu.style.top = y + "px";
    }

    function hideContextMenu() {
        contextMenu.style.display = "none";
    }

    function toggleEvents() {
        eventsEnabled = !eventsEnabled;
        if (eventsEnabled) {
            zoom.addEventListener("contextmenu", handleContextMenu);
        } else {
            zoom.removeEventListener("contextmenu", handleContextMenu);
        }
    }

    function handleContextMenu(e) {
        e.preventDefault();
        showContextMenu(e.clientX, e.clientY);
    }


    zoom.onmouseup = function () {
        if (eventsEnabled) {
            hideContextMenu();
        }
    };


    zoom.onmousemove = function (e) {

    };

});
