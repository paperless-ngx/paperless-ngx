let toggleButton
let icon

function load() {
	'use strict'

	toggleButton = document.createElement('button')
	toggleButton.setAttribute('title', 'Toggle dark mode')
	toggleButton.classList.add('dark-mode-toggle')
	icon = document.createElement('i')
	icon.classList.add('fa', darkModeState ? 'fa-sun-o' : 'fa-moon-o')
	toggleButton.appendChild(icon)
	document.body.prepend(toggleButton)

	// Listen for changes in the OS settings
	// addListener is used because older versions of Safari don't support addEventListener
	// prefersDarkQuery set in <head>
	if (prefersDarkQuery) {
		prefersDarkQuery.addListener(function (evt) {
			toggleDarkMode(evt.matches)
		})
	}

	// Initial setting depending on the prefers-color-mode or localstorage
	// darkModeState should be set in the document <head> to prevent flash
	if (darkModeState == undefined) darkModeState = false
	toggleDarkMode(darkModeState)

	// Toggles the "dark-mode" class on click and sets localStorage state
	toggleButton.addEventListener('click', () => {
		darkModeState = !darkModeState

		toggleDarkMode(darkModeState)
		localStorage.setItem('dark-mode', darkModeState)
	})
}

function toggleDarkMode(state) {
	document.documentElement.classList.toggle('dark-mode', state)
	document.documentElement.classList.toggle('light-mode', !state)
	icon.classList.remove('fa-sun-o')
	icon.classList.remove('fa-moon-o')
	icon.classList.add(state ? 'fa-sun-o' : 'fa-moon-o')
	darkModeState = state
}

document.addEventListener('DOMContentLoaded', load)
