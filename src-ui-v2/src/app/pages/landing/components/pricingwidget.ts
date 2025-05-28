import { Component } from '@angular/core'
import { ButtonModule } from 'primeng/button'
import { DividerModule } from 'primeng/divider'
import { RippleModule } from 'primeng/ripple'

@Component({
    selector: 'pricing-widget',
    imports: [DividerModule, ButtonModule, RippleModule],
    template: `
        <div id="pricing" class="py-6 px-6 lg:px-20 my-2 md:my-6">
            <div class="text-center mb-6">
                <div class="text-surface-900 dark:text-surface-0 font-normal mb-2 text-4xl">Matchless Pricing</div>
                <span class="text-muted-color text-2xl">Amet consectetur adipiscing elit...</span>
            </div>

            <div class="grid grid-cols-12 gap-4 justify-between mt-20 md:mt-0">
                <div class="col-span-12 lg:col-span-4 p-0 md:p-4">
                    <div class="p-4 flex flex-col border-surface-200 dark:border-surface-600 pricing-card cursor-pointer border-2 hover:border-primary duration-300 transition-all" style="border-radius: 10px">
                        <div class="text-surface-900 dark:text-surface-0 text-center my-8 text-3xl">Free</div>
                        <img src="https://primefaces.org/cdn/templates/sakai/landing/free.svg" class="w-10/12 mx-auto" alt="free" />
                        <div class="my-8 flex flex-col items-center gap-4">
                            <div class="flex items-center">
                                <span class="text-5xl font-bold mr-2 text-surface-900 dark:text-surface-0">$0</span>
                                <span class="text-surface-600 dark:text-surface-200">per month</span>
                            </div>
                            <button pButton pRipple label="Get Started" class="p-button-rounded border-0 ml-4 font-light leading-tight bg-blue-500 text-white"></button>
                        </div>
                        <p-divider class="w-full bg-surface-200"></p-divider>
                        <ul class="my-8 list-none p-0 flex text-surface-900 dark:text-surface-0 flex-col px-8">
                            <li class="py-2">
                                <i class="pi pi-fw pi-check text-xl text-cyan-500 mr-2"></i>
                                <span class="text-xl leading-normal">Responsive Layout</span>
                            </li>
                            <li class="py-2">
                                <i class="pi pi-fw pi-check text-xl text-cyan-500 mr-2"></i>
                                <span class="text-xl leading-normal">Unlimited Push Messages</span>
                            </li>
                            <li class="py-2">
                                <i class="pi pi-fw pi-check text-xl text-cyan-500 mr-2"></i>
                                <span class="text-xl leading-normal">50 Support Ticket</span>
                            </li>
                            <li class="py-2">
                                <i class="pi pi-fw pi-check text-xl text-cyan-500 mr-2"></i>
                                <span class="text-xl leading-normal">Free Shipping</span>
                            </li>
                        </ul>
                    </div>
                </div>

                <div class="col-span-12 lg:col-span-4 p-0 md:p-4 mt-6 md:mt-0">
                    <div class="p-4 flex flex-col border-surface-200 dark:border-surface-600 pricing-card cursor-pointer border-2 hover:border-primary duration-300 transition-all" style="border-radius: 10px">
                        <div class="text-surface-900 dark:text-surface-0 text-center my-8 text-3xl">Startup</div>
                        <img src="https://primefaces.org/cdn/templates/sakai/landing/startup.svg" class="w-10/12 mx-auto" alt="startup" />
                        <div class="my-8 flex flex-col items-center gap-4">
                            <div class="flex items-center">
                                <span class="text-5xl font-bold mr-2 text-surface-900 dark:text-surface-0">$1</span>
                                <span class="text-surface-600 dark:text-surface-200">per month</span>
                            </div>
                            <button pButton pRipple label="Get Started" class="p-button-rounded border-0 ml-4 font-light leading-tight bg-blue-500 text-white"></button>
                        </div>
                        <p-divider class="w-full bg-surface-200"></p-divider>
                        <ul class="my-8 list-none p-0 flex text-surface-900 dark:text-surface-0 flex-col px-8">
                            <li class="py-2">
                                <i class="pi pi-fw pi-check text-xl text-cyan-500 mr-2"></i>
                                <span class="text-xl leading-normal">Responsive Layout</span>
                            </li>
                            <li class="py-2">
                                <i class="pi pi-fw pi-check text-xl text-cyan-500 mr-2"></i>
                                <span class="text-xl leading-normal">Unlimited Push Messages</span>
                            </li>
                            <li class="py-2">
                                <i class="pi pi-fw pi-check text-xl text-cyan-500 mr-2"></i>
                                <span class="text-xl leading-normal">50 Support Ticket</span>
                            </li>
                            <li class="py-2">
                                <i class="pi pi-fw pi-check text-xl text-cyan-500 mr-2"></i>
                                <span class="text-xl leading-normal">Free Shipping</span>
                            </li>
                        </ul>
                    </div>
                </div>

                <div class="col-span-12 lg:col-span-4 p-0 md:p-4 mt-6 md:mt-0">
                    <div class="p-4 flex flex-col border-surface-200 dark:border-surface-600 pricing-card cursor-pointer border-2 hover:border-primary duration-300 transition-all" style="border-radius: 10px">
                        <div class="text-surface-900 dark:text-surface-0 text-center my-8 text-3xl">Enterprise</div>
                        <img src="https://primefaces.org/cdn/templates/sakai/landing/enterprise.svg" class="w-10/12 mx-auto" alt="enterprise" />
                        <div class="my-8 flex flex-col items-center gap-4">
                            <div class="flex items-center">
                                <span class="text-5xl font-bold mr-2 text-surface-900 dark:text-surface-0">$5</span>
                                <span class="text-surface-600 dark:text-surface-200">per month</span>
                            </div>
                            <button pButton pRipple label="Try Free" class="p-button-rounded border-0 ml-4 font-light leading-tight bg-blue-500 text-white"></button>
                        </div>
                        <p-divider class="w-full bg-surface-200"></p-divider>
                        <ul class="my-8 list-none p-0 flex text-surface-900 dark:text-surface-0 flex-col px-8">
                            <li class="py-2">
                                <i class="pi pi-fw pi-check text-xl text-cyan-500 mr-2"></i>
                                <span class="text-xl leading-normal">Responsive Layout</span>
                            </li>
                            <li class="py-2">
                                <i class="pi pi-fw pi-check text-xl text-cyan-500 mr-2"></i>
                                <span class="text-xl leading-normal">Unlimited Push Messages</span>
                            </li>
                            <li class="py-2">
                                <i class="pi pi-fw pi-check text-xl text-cyan-500 mr-2"></i>
                                <span class="text-xl leading-normal">50 Support Ticket</span>
                            </li>
                            <li class="py-2">
                                <i class="pi pi-fw pi-check text-xl text-cyan-500 mr-2"></i>
                                <span class="text-xl leading-normal">Free Shipping</span>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    `,
})
export class PricingWidget {
}
