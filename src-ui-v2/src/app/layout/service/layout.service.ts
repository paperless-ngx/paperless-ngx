import { computed, effect, Injectable, signal } from '@angular/core'
import { Subject } from 'rxjs'

export interface layoutConfig {
    preset?: string;
    primary?: string;
    surface?: string | undefined | null;
    darkTheme?: boolean;
    menuMode?: string;
}

interface LayoutState {
    staticMenuDesktopInactive?: boolean;
    overlayMenuActive?: boolean;
    configSidebarVisible?: boolean;
    staticMenuMobileActive?: boolean;
    menuHoverActive?: boolean;
}

interface MenuChangeEvent {
    key: string;
    routeEvent?: boolean;
}

@Injectable({
    providedIn: 'root',
})
export class LayoutService {
    _config: layoutConfig = {
        preset: 'Aura',
        primary: 'emerald',
        surface: null,
        darkTheme: false,
        menuMode: 'static',
    }

    _state: LayoutState = {
        staticMenuDesktopInactive: false,
        overlayMenuActive: false,
        configSidebarVisible: false,
        staticMenuMobileActive: false,
        menuHoverActive: false,
    }

    layoutConfig = signal<layoutConfig>(this._config)

    layoutState = signal<LayoutState>(this._state)

    private configUpdate = new Subject<layoutConfig>()

    private overlayOpen = new Subject<any>()

    private menuSource = new Subject<MenuChangeEvent>()

    private resetSource = new Subject()

    menuSource$ = this.menuSource.asObservable()

    resetSource$ = this.resetSource.asObservable()

    configUpdate$ = this.configUpdate.asObservable()

    overlayOpen$ = this.overlayOpen.asObservable()

    theme = computed(() => (this.layoutConfig()?.darkTheme ? 'light' : 'dark'))

    isSidebarActive = computed(() => this.layoutState().overlayMenuActive || this.layoutState().staticMenuMobileActive)

    isDarkTheme = computed(() => this.layoutConfig().darkTheme)

    getPrimary = computed(() => this.layoutConfig().primary)

    getSurface = computed(() => this.layoutConfig().surface)

    isOverlay = computed(() => this.layoutConfig().menuMode === 'overlay')

    transitionComplete = signal<boolean>(false)

    private initialized = false

    constructor() {
        effect(() => {
            const config = this.layoutConfig()
            if (config) {
                this.onConfigUpdate()
            }
        })

        effect(() => {
            const config = this.layoutConfig()

            if (!this.initialized || !config) {
                this.initialized = true
                return
            }

            this.handleDarkModeTransition(config)
        })
    }

    private handleDarkModeTransition(config: layoutConfig): void {
        if ((document as any).startViewTransition) {
            this.startViewTransition(config)
        } else {
            this.toggleDarkMode(config)
            this.onTransitionEnd()
        }
    }

    private startViewTransition(config: layoutConfig): void {
        const transition = (document as any).startViewTransition(() => {
            this.toggleDarkMode(config)
        })

        transition.ready
            .then(() => {
                this.onTransitionEnd()
            })
            .catch(() => {
            })
    }

    toggleDarkMode(config?: layoutConfig): void {
        const _config = config || this.layoutConfig()
        if (_config.darkTheme) {
            document.documentElement.classList.add('app-dark')
        } else {
            document.documentElement.classList.remove('app-dark')
        }
    }

    private onTransitionEnd() {
        this.transitionComplete.set(true)
        setTimeout(() => {
            this.transitionComplete.set(false)
        })
    }

    onMenuToggle() {
        if (this.isOverlay()) {
            this.layoutState.update((prev) => ({ ...prev, overlayMenuActive: !this.layoutState().overlayMenuActive }))

            if (this.layoutState().overlayMenuActive) {
                this.overlayOpen.next(null)
            }
        }

        if (this.isDesktop()) {
            this.layoutState.update((prev) => ({
                ...prev,
                staticMenuDesktopInactive: !this.layoutState().staticMenuDesktopInactive,
            }))
        } else {
            this.layoutState.update((prev) => ({
                ...prev,
                staticMenuMobileActive: !this.layoutState().staticMenuMobileActive,
            }))

            if (this.layoutState().staticMenuMobileActive) {
                this.overlayOpen.next(null)
            }
        }
    }

    isDesktop() {
        return window.innerWidth > 991
    }

    isMobile() {
        return !this.isDesktop()
    }

    onConfigUpdate() {
        this._config = { ...this.layoutConfig() }
        this.configUpdate.next(this.layoutConfig())
    }

    onMenuStateChange(event: MenuChangeEvent) {
        this.menuSource.next(event)
    }

    reset() {
        this.resetSource.next(true)
    }
}
