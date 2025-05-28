import { Component } from '@angular/core'
import { TimelineModule } from 'primeng/timeline'
import { CardModule } from 'primeng/card'
import { CommonModule } from '@angular/common'
import { ButtonModule } from 'primeng/button'

@Component({
    selector: 'app-timeline-demo',
    standalone: true,
    imports: [CommonModule, TimelineModule, ButtonModule, CardModule],
    template: ` <div class="grid grid-cols-12 gap-8">
        <div class="col-span-6">
            <div class="card">
                <div class="font-semibold text-xl mb-4">Left Align</div>
                <p-timeline [value]="events1">
                    <ng-template #content let-event>
                        {{ event.status }}
                    </ng-template>
                </p-timeline>
            </div>
        </div>
        <div class="col-span-6">
            <div class="card">
                <div class="font-semibold text-xl mb-4">Right Align</div>
                <p-timeline [value]="events1" align="right">
                    <ng-template #content let-event>
                        {{ event.status }}
                    </ng-template>
                </p-timeline>
            </div>
        </div>
        <div class="col-span-6">
            <div class="card">
                <div class="font-semibold text-xl mb-4">Alternate Align</div>
                <p-timeline [value]="events1" align="alternate">
                    <ng-template #content let-event>
                        {{ event.status }}
                    </ng-template>
                </p-timeline>
            </div>
        </div>
        <div class="col-span-6">
            <div class="card">
                <div class="font-semibold text-xl mb-4">Opposite Content</div>
                <p-timeline [value]="events1">
                    <ng-template #content let-event>
                        <small class="p-text-secondary">{{ event.date }}</small>
                    </ng-template>
                    <ng-template #opposite let-event>
                        {{ event.status }}
                    </ng-template>
                </p-timeline>
            </div>
        </div>
        <div class="col-span-full">
            <div class="card">
                <div class="font-semibold text-xl mb-4">Templating</div>
                <p-timeline [value]="events1" align="alternate" styleClass="customized-timeline">
                    <ng-template #marker let-event>
                        <span class="flex w-8 h-8 items-center justify-center text-white rounded-full z-10 shadow-sm" [style]="{ 'background-color': event.color }">
                            <i [class]="event.icon"></i>
                        </span>
                    </ng-template>
                    <ng-template #content let-event>
                        <p-card [header]="event.status" [subheader]="event.date">
                            <img *ngIf="event.image" [src]="'https://primefaces.org/cdn/primeng/images/demo/product/' + event.image" [alt]="event.name" width="200" class="shadow" />
                            <p>
                                Lorem ipsum dolor sit amet, consectetur adipisicing elit. Inventore sed consequuntur error repudiandae numquam deserunt quisquam repellat libero asperiores earum nam nobis, culpa ratione quam perferendis esse,
                                cupiditate neque quas!
                            </p>
                            <p-button label="Read more" [text]="true" />
                        </p-card>
                    </ng-template>
                </p-timeline>
            </div>
        </div>
        <div class="col-span-full">
            <div class="card">
                <div class="font-semibold text-xl mb-4">Horizontal</div>
                <div class="font-semibold mb-2">Top Align</div>
                <p-timeline [value]="events2" layout="horizontal" align="top">
                    <ng-template #content let-event>
                        {{ event }}
                    </ng-template>
                </p-timeline>

                <div class="font-semibold mt-4 mb-2">Bottom Align</div>
                <p-timeline [value]="events2" layout="horizontal" align="bottom">
                    <ng-template #content let-event>
                        {{ event }}
                    </ng-template>
                </p-timeline>

                <div class="font-semibold mt-4 mb-2">Alternate Align</div>
                <p-timeline [value]="events2" layout="horizontal" align="alternate">
                    <ng-template #content let-event>
                        {{ event }}
                    </ng-template>
                    <ng-template #opposite let-event> &nbsp; </ng-template>
                </p-timeline>
            </div>
        </div>
    </div>`,
})
export class TimelineDemo {
    events1: any[] = []

    events2: any[] = []

    ngOnInit() {
        this.events1 = [
            {
                status: 'Ordered',
                date: '15/10/2020 10:30',
                icon: 'pi pi-shopping-cart',
                color: '#9C27B0',
                image: 'game-controller.jpg',
            },
            {
                status: 'Processing',
                date: '15/10/2020 14:00',
                icon: 'pi pi-cog',
                color: '#673AB7',
            },
            {
                status: 'Shipped',
                date: '15/10/2020 16:15',
                icon: 'pi pi-envelope',
                color: '#FF9800',
            },
            {
                status: 'Delivered',
                date: '16/10/2020 10:00',
                icon: 'pi pi-check',
                color: '#607D8B',
            },
        ]

        this.events2 = ['2020', '2021', '2022', '2023']
    }
}
