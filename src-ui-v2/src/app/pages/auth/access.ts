import { Component } from '@angular/core'
import { RouterModule } from '@angular/router'
import { ButtonModule } from 'primeng/button'
import { RippleModule } from 'primeng/ripple'
import { AppFloatingConfigurator } from '../../layout/component/app.floatingconfigurator'

@Component({
    selector: 'app-access',
    standalone: true,
    imports: [ButtonModule, RouterModule, RippleModule, AppFloatingConfigurator, ButtonModule],
    template: ` <app-floating-configurator />
        <div class="bg-surface-50 dark:bg-surface-950 flex items-center justify-center min-h-screen min-w-[100vw] overflow-hidden">
            <div class="flex flex-col items-center justify-center">
                <div style="border-radius: 56px; padding: 0.3rem; background: linear-gradient(180deg, rgba(247, 149, 48, 0.4) 10%, rgba(247, 149, 48, 0) 30%)">
                    <div class="w-full bg-surface-0 dark:bg-surface-900 py-20 px-8 sm:px-20 flex flex-col items-center" style="border-radius: 53px">
                        <div class="gap-4 flex flex-col items-center">
                            <div class="flex justify-center items-center border-2 border-orange-500 rounded-full" style="width: 3.2rem; height: 3.2rem">
                                <i class="text-orange-500 pi pi-fw pi-lock !text-2xl"></i>
                            </div>
                            <h1 class="text-surface-900 dark:text-surface-0 font-bold text-4xl lg:text-5xl mb-2">Access Denied</h1>
                            <span class="text-muted-color mb-8">You do not have the necessary permisions. Please contact admins.</span>
                            <img src="https://primefaces.org/cdn/templates/sakai/auth/asset-access.svg" alt="Access denied" class="mb-8" width="80%" />
                            <div class="col-span-12 mt-8 text-center">
                                <p-button label="Go to Dashboard" routerLink="/" severity="warn" />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>`,
})
export class Access {
}
