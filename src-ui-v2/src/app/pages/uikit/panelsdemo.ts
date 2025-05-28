import { CommonModule } from '@angular/common'
import { Component } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { AccordionModule } from 'primeng/accordion'
import { MenuItem } from 'primeng/api'
import { ButtonModule } from 'primeng/button'
import { DividerModule } from 'primeng/divider'
import { FieldsetModule } from 'primeng/fieldset'
import { IconFieldModule } from 'primeng/iconfield'
import { InputIconModule } from 'primeng/inputicon'
import { InputTextModule } from 'primeng/inputtext'
import { MenuModule } from 'primeng/menu'
import { PanelModule } from 'primeng/panel'
import { RippleModule } from 'primeng/ripple'
import { SplitButtonModule } from 'primeng/splitbutton'
import { SplitterModule } from 'primeng/splitter'
import { TabsModule } from 'primeng/tabs'
import { ToolbarModule } from 'primeng/toolbar'

@Component({
    selector: 'app-panels-demo',
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        ToolbarModule,
        ButtonModule,
        RippleModule,
        SplitButtonModule,
        AccordionModule,
        FieldsetModule,
        MenuModule,
        InputTextModule,
        DividerModule,
        SplitterModule,
        PanelModule,
        TabsModule,
        IconFieldModule,
        InputIconModule,
    ],
    template: `
        <div class="flex flex-col">
            <div class="card">
                <div class="font-semibold text-xl mb-4">Toolbar</div>
                <p-toolbar>
                    <ng-template #start>
                        <p-button icon="pi pi-plus" class="mr-2" severity="secondary" text />
                        <p-button icon="pi pi-print" class="mr-2" severity="secondary" text />
                        <p-button icon="pi pi-upload" severity="secondary" text />
                    </ng-template>

                    <ng-template #center>
                        <p-iconfield>
                            <p-inputicon>
                                <i class="pi pi-search"></i>
                            </p-inputicon>
                            <input pInputText placeholder="Search" />
                        </p-iconfield>
                    </ng-template>

                    <ng-template #end><p-splitbutton label="Save" [model]="items"></p-splitbutton></ng-template>
                </p-toolbar>
            </div>

            <div class="flex flex-col md:flex-row gap-8">
                <div class="md:w-1/2">
                    <div class="card">
                        <div class="font-semibold text-xl mb-4">Accordion</div>
                        <p-accordion value="0">
                            <p-accordion-panel value="0">
                                <p-accordion-header>Header I</p-accordion-header>
                                <p-accordion-content>
                                    <p class="m-0">
                                        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex
                                        ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt
                                        mollit anim id est laborum.
                                    </p>
                                </p-accordion-content>
                            </p-accordion-panel>

                            <p-accordion-panel value="1">
                                <p-accordion-header>Header II</p-accordion-header>
                                <p-accordion-content>
                                    <p class="m-0">
                                        Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt
                                        explicabo. Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Consectetur, adipisci velit, sed quia non
                                        numquam eius modi.
                                    </p>
                                </p-accordion-content>
                            </p-accordion-panel>

                            <p-accordion-panel value="2">
                                <p-accordion-header>Header III</p-accordion-header>
                                <p-accordion-content>
                                    <p class="m-0">
                                        Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt
                                        explicabo. Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Consectetur, adipisci velit, sed quia non
                                        numquam eius modi.
                                    </p>
                                </p-accordion-content>
                            </p-accordion-panel>
                        </p-accordion>
                    </div>
                    <div class="card">
                        <div class="font-semibold text-xl mb-4">Tabs</div>
                        <p-tabs value="0">
                            <p-tablist>
                                <p-tab value="0">Header I</p-tab>
                                <p-tab value="1">Header II</p-tab>
                                <p-tab value="2">Header III</p-tab>
                            </p-tablist>
                            <p-tabpanels>
                                <p-tabpanel value="0">
                                    <p class="m-0">
                                        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex
                                        ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt
                                        mollit anim id est laborum.
                                    </p>
                                </p-tabpanel>
                                <p-tabpanel value="1">
                                    <p class="m-0">
                                        Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt
                                        explicabo. Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Consectetur, adipisci velit, sed quia non
                                        numquam eius modi.
                                    </p>
                                </p-tabpanel>
                                <p-tabpanel value="2">
                                    <p class="m-0">
                                        At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis praesentium voluptatum deleniti atque corrupti quos dolores et quas molestias excepturi sint occaecati cupiditate non provident,
                                        similique sunt in culpa qui officia deserunt mollitia animi, id est laborum et dolorum fuga. Et harum quidem rerum facilis est et expedita distinctio. Nam libero tempore, cum soluta nobis est eligendi optio
                                        cumque nihil impedit quo minus.
                                    </p>
                                </p-tabpanel>
                            </p-tabpanels>
                        </p-tabs>
                    </div>
                </div>
                <div class="md:w-1/2 mt-6 md:mt-0">
                    <div class="card">
                        <div class="font-semibold text-xl mb-4">Panel</div>
                        <p-panel header="Header" [toggleable]="true">
                            <p class="m-0">
                                Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea
                                commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim
                                id est laborum.
                            </p>
                        </p-panel>
                    </div>
                    <div class="card">
                        <div class="font-semibold text-xl mb-4">Fieldset</div>
                        <p-fieldset legend="Legend" [toggleable]="true">
                            <p class="m-0">
                                Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea
                                commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim
                                id est laborum.
                            </p>
                        </p-fieldset>
                    </div>
                </div>
            </div>

            <div class="card mt-8">
                <div class="font-semibold text-xl mb-4">Divider</div>
                <div class="flex flex-col md:flex-row">
                    <div class="w-full md:w-5/12 flex flex-col items-center justify-center gap-3 py-5">
                        <div class="flex flex-col gap-2">
                            <label for="username">Username</label>
                            <input pInputText id="username" type="text" />
                        </div>
                        <div class="flex flex-col gap-2">
                            <label for="password">Password</label>
                            <input pInputText id="password" type="password" />
                        </div>
                        <div class="flex">
                            <p-button label="Login" icon="pi pi-user" class="w-full max-w-[17.35rem] mx-auto"></p-button>
                        </div>
                    </div>
                    <div class="w-full md:w-2/12">
                        <p-divider layout="vertical" class="!hidden md:!flex"><b>OR</b></p-divider>
                        <p-divider layout="horizontal" class="!flex md:!hidden" align="center"><b>OR</b></p-divider>
                    </div>
                    <div class="w-full md:w-5/12 flex items-center justify-center py-5">
                        <p-button label="Sign Up" icon="pi pi-user-plus" severity="success" class="w-full" styleClass="w-full max-w-[17.35rem] mx-auto"></p-button>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="font-semibold text-xl mb-4">Splitter</div>
                <p-splitter [style]="{ height: '300px' }" [panelSizes]="[20, 80]" [minSizes]="[10, 0]" styleClass="mb-8">
                    <ng-template #panel>
                        <div class="col flex items-center justify-center">Panel 1</div>
                    </ng-template>
                    <ng-template #panel>
                        <p-splitter layout="vertical" [panelSizes]="[50, 50]">
                            <ng-template #panel>
                                <div style="flex-grow: 1;" class="flex items-center justify-center">Panel 2</div>
                            </ng-template>
                            <ng-template #panel>
                                <p-splitter [panelSizes]="[20, 80]">
                                    <ng-template #panel>
                                        <div class="col flex items-center justify-center">Panel 3</div>
                                    </ng-template>
                                    <ng-template #panel>
                                        <div class="col flex items-center justify-center">Panel 4</div>
                                    </ng-template>
                                </p-splitter>
                            </ng-template>
                        </p-splitter>
                    </ng-template>
                </p-splitter>
            </div>
        </div>
    `,
})
export class PanelsDemo {
    items: MenuItem[] = [
        {
            label: 'Save',
            icon: 'pi pi-check',
        },
        {
            label: 'Update',
            icon: 'pi pi-upload',
        },
        {
            label: 'Delete',
            icon: 'pi pi-trash',
        },
        {
            label: 'Home Page',
            icon: 'pi pi-home',
        },
    ]
}
