import { Component, OnInit } from '@angular/core'
import { ConfirmationService, MessageService } from 'primeng/api'
import { ButtonModule } from 'primeng/button'
import { DialogModule } from 'primeng/dialog'
import { ToastModule } from 'primeng/toast'
import { DrawerModule } from 'primeng/drawer'
import { Popover, PopoverModule } from 'primeng/popover'
import { ConfirmPopupModule } from 'primeng/confirmpopup'
import { InputTextModule } from 'primeng/inputtext'
import { FormsModule } from '@angular/forms'
import { TooltipModule } from 'primeng/tooltip'
import { TableModule } from 'primeng/table'
import { Product, ProductService } from '../service/product.service'

@Component({
    selector: 'app-overlay-demo',
    standalone: true,
    imports: [ToastModule, DialogModule, ButtonModule, DrawerModule, PopoverModule, ConfirmPopupModule, InputTextModule, FormsModule, TooltipModule, TableModule, ToastModule],
    template: ` <div class="flex flex-col md:flex-row gap-8">
        <div class="md:w-1/2">
            <div class="card">
                <div class="font-semibold text-xl mb-4">Dialog</div>
                <p-dialog header="Dialog" [(visible)]="display" [breakpoints]="{ '960px': '75vw' }" [style]="{ width: '30vw' }" [modal]="true">
                    <p class="leading-normal m-0">
                        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
                        consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
                    </p>
                    <ng-template #footer>
                        <p-button label="Save" (click)="close()" />
                    </ng-template>
                </p-dialog>
                <p-button label="Show" [style]="{ width: 'auto' }" (click)="open()" />
            </div>

            <div class="card">
                <div class="font-semibold text-xl mb-4">Popover</div>
                <div class="flex flex-wrap gap-2">
                    <p-button type="button" label="Show" (click)="toggleDataTable(op2, $event)" />
                    <p-popover #op2 id="overlay_panel" [style]="{ width: '450px' }">
                        <p-table [value]="products" selectionMode="single" [(selection)]="selectedProduct" dataKey="id" [rows]="5" [paginator]="true" (onRowSelect)="onProductSelect(op2, $event)">
                            <ng-template #header>
                                <tr>
                                    <th>Name</th>
                                    <th>Image</th>
                                    <th>Price</th>
                                </tr>
                            </ng-template>
                            <ng-template #body let-product>
                                <tr [pSelectableRow]="product">
                                    <td>{{ product.name }}</td>
                                    <td><img [src]="'https://primefaces.org/cdn/primeng/images/demo/product/' + product.image" [alt]="product.name" class="w-16 shadow-sm" /></td>
                                    <td>{{ product.price }}</td>
                                </tr>
                            </ng-template>
                        </p-table>
                    </p-popover>
                    <p-toast />
                </div>
            </div>

            <div class="card">
                <div class="font-semibold text-xl mb-4">Tooltip</div>
                <div class="inline-flex gap-4">
                    <input pInputText type="text" placeholder="Username" pTooltip="Your username" />
                    <p-button type="button" label="Save" pTooltip="Click to proceed" />
                </div>
            </div>
        </div>
        <div class="md:w-1/2">
            <div class="card">
                <div class="font-semibold text-xl mb-4">Drawer</div>
                <p-drawer [(visible)]="visibleLeft" header="Drawer">
                    <p>
                        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
                        consequat.
                    </p>
                </p-drawer>

                <p-drawer [(visible)]="visibleRight" header="Drawer" position="right">
                    <p>
                        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
                        consequat.
                    </p>
                </p-drawer>

                <p-drawer [(visible)]="visibleTop" header="Drawer" position="top">
                    <p>
                        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
                        consequat.
                    </p>
                </p-drawer>

                <p-drawer [(visible)]="visibleBottom" header="Drawer" position="bottom">
                    <p>
                        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
                        consequat.
                    </p>
                </p-drawer>

                <p-drawer [(visible)]="visibleFull" header="Drawer" position="full">
                    <p>
                        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
                        consequat.
                    </p>
                </p-drawer>

                <p-button icon="pi pi-arrow-right" (click)="visibleLeft = true" [style]="{ marginRight: '0.25em' }" />
                <p-button icon="pi pi-arrow-left" (click)="visibleRight = true" [style]="{ marginRight: '0.25em' }" />
                <p-button icon="pi pi-arrow-down" (click)="visibleTop = true" [style]="{ marginRight: '0.25em' }" />
                <p-button icon="pi pi-arrow-up" (click)="visibleBottom = true" [style]="{ marginRight: '0.25em' }" />
                <p-button icon="pi pi-external-link" (click)="visibleFull = true" />
            </div>

            <div class="card">
                <div class="font-semibold text-xl mb-4">ConfirmPopup</div>
                <p-confirmpopup></p-confirmpopup>
                <p-button #popup (click)="confirm($event)" icon="pi pi-check" label="Confirm" class="mr-2"></p-button>
            </div>

            <div class="card">
                <div class="font-semibold text-xl mb-4">ConfirmDialog</div>
                <p-button label="Delete" icon="pi pi-trash" severity="danger" [style]="{ width: 'auto' }" (click)="openConfirmation()" />
                <p-dialog header="Confirmation" [(visible)]="displayConfirmation" [style]="{ width: '350px' }" [modal]="true">
                    <div class="flex items-center justify-center">
                        <i class="pi pi-exclamation-triangle mr-4" style="font-size: 2rem"> </i>
                        <span>Are you sure you want to proceed?</span>
                    </div>
                    <ng-template #footer>
                        <p-button label="No" icon="pi pi-times" (click)="closeConfirmation()" text severity="secondary" />
                        <p-button label="Yes" icon="pi pi-check" (click)="closeConfirmation()" severity="danger" outlined autofocus />
                    </ng-template>
                </p-dialog>
            </div>
        </div>
    </div>`,
    providers: [ConfirmationService, MessageService, ProductService],
})
export class OverlayDemo implements OnInit {
    images: any[] = []

    display: boolean = false

    products: Product[] = []

    visibleLeft: boolean = false

    visibleRight: boolean = false

    visibleTop: boolean = false

    visibleBottom: boolean = false

    visibleFull: boolean = false

    displayConfirmation: boolean = false

    selectedProduct!: Product

    constructor(
        private productService: ProductService,
        private confirmationService: ConfirmationService,
        private messageService: MessageService,
    ) {
    }

    ngOnInit() {
        this.productService.getProductsSmall().then((products) => (this.products = products))

        this.images = []
        this.images.push({
            source: 'assets/demo/images/sopranos/sopranos1.jpg',
            thumbnail: 'assets/demo/images/sopranos/sopranos1_small.jpg',
            title: 'Sopranos 1',
        })
        this.images.push({
            source: 'assets/demo/images/sopranos/sopranos2.jpg',
            thumbnail: 'assets/demo/images/sopranos/sopranos2_small.jpg',
            title: 'Sopranos 2',
        })
        this.images.push({
            source: 'assets/demo/images/sopranos/sopranos3.jpg',
            thumbnail: 'assets/demo/images/sopranos/sopranos3_small.jpg',
            title: 'Sopranos 3',
        })
        this.images.push({
            source: 'assets/demo/images/sopranos/sopranos4.jpg',
            thumbnail: 'assets/demo/images/sopranos/sopranos4_small.jpg',
            title: 'Sopranos 4',
        })
    }

    confirm(event: Event) {
        this.confirmationService.confirm({
            key: 'confirm2',
            target: event.target || new EventTarget(),
            message: 'Are you sure that you want to proceed?',
            icon: 'pi pi-exclamation-triangle',
            accept: () => {
                this.messageService.add({ severity: 'info', summary: 'Confirmed', detail: 'You have accepted' })
            },
            reject: () => {
                this.messageService.add({ severity: 'error', summary: 'Rejected', detail: 'You have rejected' })
            },
        })
    }

    open() {
        this.display = true
    }

    close() {
        this.display = false
    }

    toggleDataTable(op: Popover, event: any) {
        op.toggle(event)
    }

    onProductSelect(op: Popover, event: any) {
        op.hide()
        this.messageService.add({
            severity: 'info',
            summary: 'Product Selected',
            detail: event?.data.name,
            life: 3000,
        })
    }

    openConfirmation() {
        this.displayConfirmation = true
    }

    closeConfirmation() {
        this.displayConfirmation = false
    }
}
