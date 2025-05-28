import { Component, Renderer2, ViewChild } from '@angular/core'
import { CommonModule } from '@angular/common'
import { NavigationEnd, Router, RouterModule } from '@angular/router'
import { filter, Subscription } from 'rxjs'
import { AppTopbar } from './app.topbar'
import { AppSidebar } from './app.sidebar'
import { AppFooter } from './app.footer'
import { LayoutService } from '../service/layout.service'

@Component({
    selector: 'app-layout',
    standalone: true,
    imports: [CommonModule, AppTopbar, AppSidebar, RouterModule, AppFooter],
    template: `<div class="layout-wrapper" [ngClass]="containerClass">
        <app-topbar></app-topbar>
        <app-sidebar></app-sidebar>
        <div class="layout-main-container">
            <div class="layout-main">
                <router-outlet></router-outlet>
            </div>
            <app-footer></app-footer>
        </div>
        <div class="layout-mask animate-fadein"></div>
    </div> `,
})
export class AppLayout {
    overlayMenuOpenSubscription: Subscription

    menuOutsideClickListener: any

    @ViewChild(AppSidebar) appSidebar!: AppSidebar

    @ViewChild(AppTopbar) appTopBar!: AppTopbar

    constructor(
        public layoutService: LayoutService,
        public renderer: Renderer2,
        public router: Router,
    ) {
        this.overlayMenuOpenSubscription = this.layoutService.overlayOpen$.subscribe(() => {
            if (!this.menuOutsideClickListener) {
                this.menuOutsideClickListener = this.renderer.listen('document', 'click', (event) => {
                    if (this.isOutsideClicked(event)) {
                        this.hideMenu()
                    }
                })
            }

            if (this.layoutService.layoutState().staticMenuMobileActive) {
                this.blockBodyScroll()
            }
        })

        this.router.events.pipe(filter((event) => event instanceof NavigationEnd)).subscribe(() => {
            this.hideMenu()
        })
    }

    isOutsideClicked(event: MouseEvent) {
        const sidebarEl = document.querySelector('.layout-sidebar')
        const topbarEl = document.querySelector('.layout-menu-button')
        const eventTarget = event.target as Node

        return !(sidebarEl?.isSameNode(eventTarget) || sidebarEl?.contains(eventTarget) || topbarEl?.isSameNode(eventTarget) || topbarEl?.contains(eventTarget))
    }

    hideMenu() {
        this.layoutService.layoutState.update((prev) => ({
            ...prev,
            overlayMenuActive: false,
            staticMenuMobileActive: false,
            menuHoverActive: false,
        }))
        if (this.menuOutsideClickListener) {
            this.menuOutsideClickListener()
            this.menuOutsideClickListener = null
        }
        this.unblockBodyScroll()
    }

    blockBodyScroll(): void {
        if (document.body.classList) {
            document.body.classList.add('blocked-scroll')
        } else {
            document.body.className += ' blocked-scroll'
        }
    }

    unblockBodyScroll(): void {
        if (document.body.classList) {
            document.body.classList.remove('blocked-scroll')
        } else {
            document.body.className = document.body.className.replace(new RegExp('(^|\\b)' + 'blocked-scroll'.split(' ').join('|') + '(\\b|$)', 'gi'), ' ')
        }
    }

    get containerClass() {
        return {
            'layout-overlay': this.layoutService.layoutConfig().menuMode === 'overlay',
            'layout-static': this.layoutService.layoutConfig().menuMode === 'static',
            'layout-static-inactive': this.layoutService.layoutState().staticMenuDesktopInactive && this.layoutService.layoutConfig().menuMode === 'static',
            'layout-overlay-active': this.layoutService.layoutState().overlayMenuActive,
            'layout-mobile-active': this.layoutService.layoutState().staticMenuMobileActive,
        }
    }

    ngOnDestroy() {
        if (this.overlayMenuOpenSubscription) {
            this.overlayMenuOpenSubscription.unsubscribe()
        }

        if (this.menuOutsideClickListener) {
            this.menuOutsideClickListener()
        }
    }
}
