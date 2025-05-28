import { Component } from '@angular/core'
import { CommonModule } from '@angular/common'
import { ButtonModule } from 'primeng/button'
import { MenuModule } from 'primeng/menu'

@Component({
    standalone: true,
    selector: 'app-best-selling-widget',
    imports: [CommonModule, ButtonModule, MenuModule],
    template: ` <div class="card">
        <div class="flex justify-between items-center mb-6">
            <div class="font-semibold text-xl">Best Selling Products</div>
            <div>
                <button pButton type="button" icon="pi pi-ellipsis-v" class="p-button-rounded p-button-text p-button-plain" (click)="menu.toggle($event)"></button>
                <p-menu #menu [popup]="true" [model]="items"></p-menu>
            </div>
        </div>
        <ul class="list-none p-0 m-0">
            <li class="flex flex-col md:flex-row md:items-center md:justify-between mb-6">
                <div>
                    <span class="text-surface-900 dark:text-surface-0 font-medium mr-2 mb-1 md:mb-0">Space T-Shirt</span>
                    <div class="mt-1 text-muted-color">Clothing</div>
                </div>
                <div class="mt-2 md:mt-0 flex items-center">
                    <div class="bg-surface-300 dark:bg-surface-500 rounded-border overflow-hidden w-40 lg:w-24" style="height: 8px">
                        <div class="bg-orange-500 h-full" style="width: 50%"></div>
                    </div>
                    <span class="text-orange-500 ml-4 font-medium">%50</span>
                </div>
            </li>
            <li class="flex flex-col md:flex-row md:items-center md:justify-between mb-6">
                <div>
                    <span class="text-surface-900 dark:text-surface-0 font-medium mr-2 mb-1 md:mb-0">Portal Sticker</span>
                    <div class="mt-1 text-muted-color">Accessories</div>
                </div>
                <div class="mt-2 md:mt-0 ml-0 md:ml-20 flex items-center">
                    <div class="bg-surface-300 dark:bg-surface-500 rounded-border overflow-hidden w-40 lg:w-24" style="height: 8px">
                        <div class="bg-cyan-500 h-full" style="width: 16%"></div>
                    </div>
                    <span class="text-cyan-500 ml-4 font-medium">%16</span>
                </div>
            </li>
            <li class="flex flex-col md:flex-row md:items-center md:justify-between mb-6">
                <div>
                    <span class="text-surface-900 dark:text-surface-0 font-medium mr-2 mb-1 md:mb-0">Supernova Sticker</span>
                    <div class="mt-1 text-muted-color">Accessories</div>
                </div>
                <div class="mt-2 md:mt-0 ml-0 md:ml-20 flex items-center">
                    <div class="bg-surface-300 dark:bg-surface-500 rounded-border overflow-hidden w-40 lg:w-24" style="height: 8px">
                        <div class="bg-pink-500 h-full" style="width: 67%"></div>
                    </div>
                    <span class="text-pink-500 ml-4 font-medium">%67</span>
                </div>
            </li>
            <li class="flex flex-col md:flex-row md:items-center md:justify-between mb-6">
                <div>
                    <span class="text-surface-900 dark:text-surface-0 font-medium mr-2 mb-1 md:mb-0">Wonders Notebook</span>
                    <div class="mt-1 text-muted-color">Office</div>
                </div>
                <div class="mt-2 md:mt-0 ml-0 md:ml-20 flex items-center">
                    <div class="bg-surface-300 dark:bg-surface-500 rounded-border overflow-hidden w-40 lg:w-24" style="height: 8px">
                        <div class="bg-green-500 h-full" style="width: 35%"></div>
                    </div>
                    <span class="text-primary ml-4 font-medium">%35</span>
                </div>
            </li>
            <li class="flex flex-col md:flex-row md:items-center md:justify-between mb-6">
                <div>
                    <span class="text-surface-900 dark:text-surface-0 font-medium mr-2 mb-1 md:mb-0">Mat Black Case</span>
                    <div class="mt-1 text-muted-color">Accessories</div>
                </div>
                <div class="mt-2 md:mt-0 ml-0 md:ml-20 flex items-center">
                    <div class="bg-surface-300 dark:bg-surface-500 rounded-border overflow-hidden w-40 lg:w-24" style="height: 8px">
                        <div class="bg-purple-500 h-full" style="width: 75%"></div>
                    </div>
                    <span class="text-purple-500 ml-4 font-medium">%75</span>
                </div>
            </li>
            <li class="flex flex-col md:flex-row md:items-center md:justify-between mb-6">
                <div>
                    <span class="text-surface-900 dark:text-surface-0 font-medium mr-2 mb-1 md:mb-0">Robots T-Shirt</span>
                    <div class="mt-1 text-muted-color">Clothing</div>
                </div>
                <div class="mt-2 md:mt-0 ml-0 md:ml-20 flex items-center">
                    <div class="bg-surface-300 dark:bg-surface-500 rounded-border overflow-hidden w-40 lg:w-24" style="height: 8px">
                        <div class="bg-teal-500 h-full" style="width: 40%"></div>
                    </div>
                    <span class="text-teal-500 ml-4 font-medium">%40</span>
                </div>
            </li>
        </ul>
    </div>`,
})
export class BestSellingWidget {
    menu = null

    items = [
        { label: 'Add New', icon: 'pi pi-fw pi-plus' },
        { label: 'Remove', icon: 'pi pi-fw pi-trash' },
    ]
}
