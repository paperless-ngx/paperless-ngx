import { Component, ElementRef, OnInit, ViewChild } from '@angular/core'
import { ConfirmationService, MessageService } from 'primeng/api'
import { InputTextModule } from 'primeng/inputtext'
import { MultiSelectModule } from 'primeng/multiselect'
import { SelectModule } from 'primeng/select'
import { SliderModule } from 'primeng/slider'
import { Table, TableModule } from 'primeng/table'
import { ProgressBarModule } from 'primeng/progressbar'
import { ToggleButtonModule } from 'primeng/togglebutton'
import { ToastModule } from 'primeng/toast'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { ButtonModule } from 'primeng/button'
import { RatingModule } from 'primeng/rating'
import { RippleModule } from 'primeng/ripple'
import { InputIconModule } from 'primeng/inputicon'
import { IconFieldModule } from 'primeng/iconfield'
import { TagModule } from 'primeng/tag'
import { Customer, CustomerService, Representative } from '../service/customer.service'
import { Product, ProductService } from '../service/product.service'

interface expandedRows {
    [key: string]: boolean;
}

@Component({
    selector: 'app-table-demo',
    standalone: true,
    imports: [
        TableModule,
        MultiSelectModule,
        SelectModule,
        InputIconModule,
        TagModule,
        InputTextModule,
        SliderModule,
        ProgressBarModule,
        ToggleButtonModule,
        ToastModule,
        CommonModule,
        FormsModule,
        ButtonModule,
        RatingModule,
        RippleModule,
        IconFieldModule,
    ],
    template: ` <div class="card">
            <div class="font-semibold text-xl mb-4">Filtering</div>
            <p-table
                #dt1
                [value]="customers1"
                dataKey="id"
                [rows]="10"
                [loading]="loading"
                [rowHover]="true"
                [showGridlines]="true"
                [paginator]="true"
                [globalFilterFields]="['name', 'country.name', 'representative.name', 'status']"
                responsiveLayout="scroll"
            >
                <ng-template #caption>
                    <div class="flex justify-between items-center flex-column sm:flex-row">
                        <button pButton label="Clear" class="p-button-outlined mb-2" icon="pi pi-filter-slash" (click)="clear(dt1)"></button>
                        <p-iconfield iconPosition="left" class="ml-auto">
                            <p-inputicon>
                                <i class="pi pi-search"></i>
                            </p-inputicon>
                            <input pInputText type="text" (input)="onGlobalFilter(dt1, $event)" placeholder="Search keyword" />
                        </p-iconfield>
                    </div>
                </ng-template>
                <ng-template #header>
                    <tr>
                        <th style="min-width: 12rem">
                            <div class="flex justify-between items-center">
                                Name
                                <p-columnFilter type="text" field="name" display="menu" placeholder="Search by name"></p-columnFilter>
                            </div>
                        </th>
                        <th style="min-width: 12rem">
                            <div class="flex justify-between items-center">
                                Country
                                <p-columnFilter type="text" field="country.name" display="menu" placeholder="Search by country"></p-columnFilter>
                            </div>
                        </th>
                        <th style="min-width: 14rem">
                            <div class="flex justify-between items-center">
                                Agent
                                <p-columnFilter field="representative" matchMode="in" display="menu" [showMatchModes]="false" [showOperator]="false" [showAddButton]="false">
                                    <ng-template #header>
                                        <div class="px-3 pt-3 pb-0">
                                            <span class="font-bold">Agent Picker</span>
                                        </div>
                                    </ng-template>
                                    <ng-template #filter let-value let-filter="filterCallback">
                                        <p-multiselect [ngModel]="value" [options]="representatives" placeholder="Any" (onChange)="filter($event.value)" optionLabel="name" styleClass="w-full">
                                            <ng-template let-option #item>
                                                <div class="flex items-center gap-2 w-44">
                                                    <img [alt]="option.label" src="https://primefaces.org/cdn/primeng/images/demo/avatar/{{ option.image }}" width="32" />
                                                    <span>{{ option.name }}</span>
                                                </div>
                                            </ng-template>
                                        </p-multiselect>
                                    </ng-template>
                                </p-columnFilter>
                            </div>
                        </th>
                        <th style="min-width: 10rem">
                            <div class="flex justify-between items-center">
                                Date
                                <p-columnFilter type="date" field="date" display="menu" placeholder="mm/dd/yyyy"></p-columnFilter>
                            </div>
                        </th>
                        <th style="min-width: 10rem">
                            <div class="flex justify-between items-center">
                                Balance
                                <p-columnFilter type="numeric" field="balance" display="menu" currency="USD"></p-columnFilter>
                            </div>
                        </th>
                        <th style="min-width: 12rem">
                            <div class="flex justify-between items-center">
                                Status
                                <p-columnFilter field="status" matchMode="equals" display="menu">
                                    <ng-template #filter let-value let-filter="filterCallback">
                                        <p-select [ngModel]="value" [options]="statuses" (onChange)="filter($event.value)" placeholder="Any" [style]="{ 'min-width': '12rem' }">
                                            <ng-template let-option #item>
                                                <span [class]="'customer-badge status-' + option.value">{{ option.label }}</span>
                                            </ng-template>
                                        </p-select>
                                    </ng-template>
                                </p-columnFilter>
                            </div>
                        </th>
                        <th style="min-width: 12rem">
                            <div class="flex justify-between items-center">
                                Activity
                                <p-columnFilter field="activity" matchMode="between" display="menu" [showMatchModes]="false" [showOperator]="false" [showAddButton]="false">
                                    <ng-template #filter let-filter="filterCallback">
                                        <p-slider [ngModel]="activityValues" [range]="true" (onSlideEnd)="filter($event.values)" styleClass="m-3" [style]="{ 'min-width': '12rem' }"></p-slider>
                                        <div class="flex items-center justify-between px-2">
                                            <span>{{ activityValues[0] }}</span>
                                            <span>{{ activityValues[1] }}</span>
                                        </div>
                                    </ng-template>
                                </p-columnFilter>
                            </div>
                        </th>
                        <th style="min-width: 8rem">
                            <div class="flex justify-between items-center">
                                Verified
                                <p-columnFilter type="boolean" field="verified" display="menu"></p-columnFilter>
                            </div>
                        </th>
                    </tr>
                </ng-template>
                <ng-template #body let-customer>
                    <tr>
                        <td>
                            {{ customer.name }}
                        </td>
                        <td>
                            <div class="flex items-center gap-2">
                                <img src="https://primefaces.org/cdn/primeng/images/demo/flag/flag_placeholder.png" [class]="'flag flag-' + customer.country.code" width="30" />
                                <span>{{ customer.country.name }}</span>
                            </div>
                        </td>
                        <td>
                            <div class="flex items-center gap-2">
                                <img [alt]="customer.representative.name" src="https://primefaces.org/cdn/primeng/images/demo/avatar/{{ customer.representative.image }}" width="32" style="vertical-align: middle" />
                                <span class="image-text">{{ customer.representative.name }}</span>
                            </div>
                        </td>
                        <td>
                            {{ customer.date | date: 'MM/dd/yyyy' }}
                        </td>
                        <td>
                            {{ customer.balance | currency: 'USD' : 'symbol' }}
                        </td>
                        <td>
                            <p-tag [value]="customer.status.toLowerCase()" [severity]="getSeverity(customer.status.toLowerCase())" styleClass="dark:!bg-surface-900" />
                        </td>
                        <td>
                            <p-progressbar [value]="customer.activity" [showValue]="false" [style]="{ height: '0.5rem' }" />
                        </td>
                        <td class="text-center">
                            <p-tag [value]="customer.status.toLowerCase()" [severity]="getSeverity(customer.status.toLowerCase())" styleClass="dark:!bg-surface-900" />
                        </td>
                    </tr>
                </ng-template>
                <ng-template #emptymessage>
                    <tr>
                        <td colspan="8">No customers found.</td>
                    </tr>
                </ng-template>
                <ng-template #loadingbody>
                    <tr>
                        <td colspan="8">Loading customers data. Please wait.</td>
                    </tr>
                </ng-template>
            </p-table>
        </div>

        <div class="card">
            <div class="font-semibold text-xl mb-4">Frozen Columns</div>
            <p-togglebutton [(ngModel)]="balanceFrozen" [onIcon]="'pi pi-lock'" offIcon="pi pi-lock-open" [onLabel]="'Balance'" offLabel="Balance" />

            <p-table [value]="customers2" [scrollable]="true" scrollHeight="400px" styleClass="mt-4">
                <ng-template #header>
                    <tr>
                        <th style="min-width:200px" pFrozenColumn class="font-bold">Name</th>
                        <th style="min-width:100px">Id</th>
                        <th style="min-width:200px">Country</th>
                        <th style="min-width:200px">Date</th>
                        <th style="min-width:200px">Company</th>
                        <th style="min-width:200px">Status</th>
                        <th style="min-width:200px">Activity</th>
                        <th style="min-width:200px">Representative</th>
                        <th style="min-width:200px" alignFrozen="right" pFrozenColumn [frozen]="balanceFrozen" [ngClass]="{ 'font-bold': balanceFrozen }">Balance</th>
                    </tr>
                </ng-template>
                <ng-template #body let-customer>
                    <tr>
                        <td pFrozenColumn class="font-bold">{{ customer.name }}</td>
                        <td style="min-width:100px">{{ customer.id }}</td>
                        <td>{{ customer.country.name }}</td>
                        <td>{{ customer.date }}</td>
                        <td>{{ customer.company }}</td>
                        <td>{{ customer.status }}</td>
                        <td>{{ customer.activity }}</td>
                        <td>{{ customer.representative.name }}</td>
                        <td alignFrozen="right" pFrozenColumn [frozen]="balanceFrozen" [ngClass]="{ 'font-bold': balanceFrozen }">
                            {{ formatCurrency(customer.balance) }}
                        </td>
                    </tr>
                </ng-template>
            </p-table>
        </div>

        <div class="card">
            <div class="font-semibold text-xl mb-4">Row Expansion</div>
            <p-table [value]="products" dataKey="name" [expandedRowKeys]="expandedRows" responsiveLayout="scroll">
                <ng-template #caption>
                    <button pButton icon="pi pi-fw {{ isExpanded ? 'pi-minus' : 'pi-plus' }}" label="{{ isExpanded ? 'Collapse All' : 'Expand All' }}" (click)="expandAll()"></button>
                    <div class="flex table-header"></div>
                </ng-template>
                <ng-template #header>
                    <tr>
                        <th style="width: 3rem"></th>
                        <th pSortableColumn="name">
                            Name
                            <p-sortIcon field="name"></p-sortIcon>
                        </th>
                        <th>Image</th>
                        <th pSortableColumn="price">
                            Price
                            <p-sortIcon field="price"></p-sortIcon>
                        </th>
                        <th pSortableColumn="category">
                            Category
                            <p-sortIcon field="category"></p-sortIcon>
                        </th>
                        <th pSortableColumn="rating">
                            Reviews
                            <p-sortIcon field="rating"></p-sortIcon>
                        </th>
                        <th pSortableColumn="inventoryStatus">
                            Status
                            <p-sortIcon field="inventoryStatus"></p-sortIcon>
                        </th>
                    </tr>
                </ng-template>
                <ng-template #body let-product let-expanded="expanded">
                    <tr>
                        <td>
                            <button type="button" pButton pRipple [pRowToggler]="product" class="p-button-text p-button-rounded p-button-plain" [icon]="expanded ? 'pi pi-chevron-down' : 'pi pi-chevron-right'"></button>
                        </td>
                        <td style="min-width: 12rem;">{{ product.name }}</td>
                        <td><img [src]="'https://primefaces.org/cdn/primeng/images/demo/product/' + product.image" [alt]="product.name" width="50" class="shadow-lg" /></td>
                        <td style="min-width: 8rem;">{{ product.price | currency: 'USD' }}</td>
                        <td style="min-width: 10rem;">{{ product.category }}</td>
                        <td style="min-width: 10rem;">
                            <p-rating [ngModel]="product.rating" [readonly]="true"></p-rating>
                        </td>
                        <td>
                            <p-tag [value]="product.inventoryStatus.toLowerCase()" [severity]="getSeverity(product.inventoryStatus)" styleClass="dark:!bg-surface-900" />
                        </td>
                    </tr>
                </ng-template>
                <ng-template #rowexpansion let-product>
                    <tr>
                        <td colspan="7">
                            <div class="p-3">
                                <p-table [value]="product.orders" dataKey="id" responsiveLayout="scroll">
                                    <ng-template #header>
                                        <tr>
                                            <th pSortableColumn="id">
                                                Id
                                                <p-sortIcon field="price"></p-sortIcon>
                                            </th>
                                            <th pSortableColumn="customer">
                                                Customer
                                                <p-sortIcon field="customer"></p-sortIcon>
                                            </th>
                                            <th pSortableColumn="date">
                                                Date
                                                <p-sortIcon field="date"></p-sortIcon>
                                            </th>
                                            <th pSortableColumn="amount">
                                                Amount
                                                <p-sortIcon field="amount"></p-sortIcon>
                                            </th>
                                            <th pSortableColumn="stats">
                                                Status
                                                <p-sortIcon field="status"></p-sortIcon>
                                            </th>
                                            <th style="width: 4rem"></th>
                                        </tr>
                                    </ng-template>
                                    <ng-template #body let-order>
                                        <tr>
                                            <td>{{ order.id }}</td>
                                            <td>{{ order.customer }}</td>
                                            <td>{{ order.date }}</td>
                                            <td>{{ order.amount | currency: 'USD' }}</td>
                                            <td>
                                                <span [class]="'order-badge order-' + order.status.toLowerCase()">{{ order.status }}</span>
                                            </td>
                                            <td>
                                                <p-button type="button" icon="pi pi-search"></p-button>
                                            </td>
                                        </tr>
                                    </ng-template>
                                    <ng-template #emptymessage>
                                        <tr>
                                            <td colspan="6">There are no order for this product yet.</td>
                                        </tr>
                                    </ng-template>
                                </p-table>
                            </div>
                        </td>
                    </tr>
                </ng-template>
            </p-table>
        </div>

        <div class="card">
            <div class="font-semibold text-xl mb-4">Grouping</div>
            <p-table [value]="customers3" sortField="representative.name" sortMode="single" [scrollable]="true" scrollHeight="400px" rowGroupMode="subheader" groupRowsBy="representative.name" [tableStyle]="{ 'min-width': '60rem' }">
                <ng-template #header>
                    <tr>
                        <th>Name</th>
                        <th>Country</th>
                        <th>Company</th>
                        <th>Status</th>
                        <th>Date</th>
                    </tr>
                </ng-template>
                <ng-template #groupheader let-customer>
                    <tr pRowGroupHeader>
                        <td colspan="5">
                            <div class="flex items-center gap-2">
                                <img [alt]="customer.representative.name" src="https://primefaces.org/cdn/primeng/images/demo/avatar/{{ customer.representative.image }}" width="32" style="vertical-align: middle" />
                                <span class="font-bold">{{ customer.representative.name }}</span>
                            </div>
                        </td>
                    </tr>
                </ng-template>
                <ng-template #groupfooter let-customer>
                    <tr>
                        <td colspan="5" class="text-right font-bold pr-12">Total Customers: {{ calculateCustomerTotal(customer.representative.name) }}</td>
                    </tr>
                </ng-template>
                <ng-template #body let-customer let-rowIndex="rowIndex">
                    <tr>
                        <td>
                            {{ customer.name }}
                        </td>
                        <td>
                            <div class="flex items-center gap-2">
                                <img src="https://primefaces.org/cdn/primeng/images/demo/flag/flag_placeholder.png" [class]="'flag flag-' + customer.country.code" style="width: 20px" />
                                <span>{{ customer.country.name }}</span>
                            </div>
                        </td>
                        <td>
                            {{ customer.company }}
                        </td>
                        <td>
                            <p-tag [value]="customer.status" [severity]="getSeverity(customer.status)" />
                        </td>
                        <td>
                            {{ customer.date }}
                        </td>
                    </tr>
                </ng-template>
            </p-table>
        </div>`,
    styles: `
        .p-datatable-frozen-tbody {
            font-weight: bold;
        }

        .p-datatable-scrollable .p-frozen-column {
            font-weight: bold;
        }
    `,
    providers: [ConfirmationService, MessageService, CustomerService, ProductService],
})
export class TableDemo implements OnInit {
    customers1: Customer[] = []

    customers2: Customer[] = []

    customers3: Customer[] = []

    selectedCustomers1: Customer[] = []

    selectedCustomer: Customer = {}

    representatives: Representative[] = []

    statuses: any[] = []

    products: Product[] = []

    rowGroupMetadata: any

    expandedRows: expandedRows = {}

    activityValues: number[] = [0, 100]

    isExpanded: boolean = false

    balanceFrozen: boolean = false

    loading: boolean = true

    @ViewChild('filter') filter!: ElementRef

    constructor(
        private customerService: CustomerService,
        private productService: ProductService,
    ) {
    }

    ngOnInit() {
        this.customerService.getCustomersLarge().then((customers) => {
            this.customers1 = customers
            this.loading = false

            // @ts-ignore
            this.customers1.forEach((customer) => (customer.date = new Date(customer.date)))
        })
        this.customerService.getCustomersMedium().then((customers) => (this.customers2 = customers))
        this.customerService.getCustomersLarge().then((customers) => (this.customers3 = customers))
        this.productService.getProductsWithOrdersSmall().then((data) => (this.products = data))

        this.representatives = [
            { name: 'Amy Elsner', image: 'amyelsner.png' },
            { name: 'Anna Fali', image: 'annafali.png' },
            { name: 'Asiya Javayant', image: 'asiyajavayant.png' },
            { name: 'Bernardo Dominic', image: 'bernardodominic.png' },
            { name: 'Elwin Sharvill', image: 'elwinsharvill.png' },
            { name: 'Ioni Bowcher', image: 'ionibowcher.png' },
            { name: 'Ivan Magalhaes', image: 'ivanmagalhaes.png' },
            { name: 'Onyama Limba', image: 'onyamalimba.png' },
            { name: 'Stephen Shaw', image: 'stephenshaw.png' },
            { name: 'XuXue Feng', image: 'xuxuefeng.png' },
        ]

        this.statuses = [
            { label: 'Unqualified', value: 'unqualified' },
            { label: 'Qualified', value: 'qualified' },
            { label: 'New', value: 'new' },
            { label: 'Negotiation', value: 'negotiation' },
            { label: 'Renewal', value: 'renewal' },
            { label: 'Proposal', value: 'proposal' },
        ]
    }

    onSort() {
        this.updateRowGroupMetaData()
    }

    updateRowGroupMetaData() {
        this.rowGroupMetadata = {}

        if (this.customers3) {
            for (let i = 0; i < this.customers3.length; i++) {
                const rowData = this.customers3[i]
                const representativeName = rowData?.representative?.name || ''

                if (i === 0) {
                    this.rowGroupMetadata[representativeName] = { index: 0, size: 1 }
                } else {
                    const previousRowData = this.customers3[i - 1]
                    const previousRowGroup = previousRowData?.representative?.name
                    if (representativeName === previousRowGroup) {
                        this.rowGroupMetadata[representativeName].size++
                    } else {
                        this.rowGroupMetadata[representativeName] = { index: i, size: 1 }
                    }
                }
            }
        }
    }

    expandAll() {
        if (!this.isExpanded) {
            this.products.forEach((product) => (product && product.name ? (this.expandedRows[product.name] = true) : ''))
        } else {
            this.expandedRows = {}
        }
        this.isExpanded = !this.isExpanded
    }

    formatCurrency(value: number) {
        return value.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
    }

    onGlobalFilter(table: Table, event: Event) {
        table.filterGlobal((event.target as HTMLInputElement).value, 'contains')
    }

    clear(table: Table) {
        table.clear()
        this.filter.nativeElement.value = ''
    }

    getSeverity(status: string) {
        switch (status) {
            case 'qualified':
            case 'instock':
            case 'INSTOCK':
            case 'DELIVERED':
            case 'delivered':
                return 'success'

            case 'negotiation':
            case 'lowstock':
            case 'LOWSTOCK':
            case 'PENDING':
            case 'pending':
                return 'warn'

            case 'unqualified':
            case 'outofstock':
            case 'OUTOFSTOCK':
            case 'CANCELLED':
            case 'cancelled':
                return 'danger'

            default:
                return 'info'
        }
    }

    calculateCustomerTotal(name: string) {
        let total = 0

        if (this.customers2) {
            for (let customer of this.customers2) {
                if (customer.representative?.name === name) {
                    total++
                }
            }
        }

        return total
    }
}
