import { DatePipe } from '@angular/common'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap'
import { of } from 'rxjs'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SortableDirective } from 'src/app/directives/sortable.directive'
import { WarehouseService } from 'src/app/services/rest/warehouse.service'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { WarehouseListComponent } from './warehouse-list.component'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'

describe('WarehouseListComponent', () => {
  let component: WarehouseListComponent
  let fixture: ComponentFixture<WarehouseListComponent>
  let warehouseService: WarehouseService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        WarehouseListComponent,
        SortableDirective,
        PageHeaderComponent,
        IfPermissionsDirective,
        SafeHtmlPipe,
      ],
      providers: [DatePipe],
      imports: [
        HttpClientTestingModule,
        NgbPaginationModule,
        FormsModule,
        ReactiveFormsModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    }).compileComponents()

    warehouseService = TestBed.inject(WarehouseService)
    jest.spyOn(warehouseService, 'listFiltered').mockReturnValue(
      of({
        count: 3,
        all: [1, 2, 3],
        results: [
          {
            id: 1,
            name: 'Warehouse1',
          },
          {
            id: 2,
            name: 'Warehouse2',
          },
          {
            id: 3,
            name: 'Warehouse3',
          },
        ],
      })
    )
    fixture = TestBed.createComponent(WarehouseListComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  // Tests are included in management-list.component.spec.ts

  it('should use correct delete message', () => {
    expect(component.getDeleteMessage({ id: 1, name: 'Warehouse1' })).toEqual(
      'Do you really want to delete the warehouse "Warehouse1"?'
    )
  })
})
