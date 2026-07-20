import { DatePipe } from '@angular/common'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of } from 'rxjs'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SortableDirective } from 'src/app/directives/sortable.directive'
import { NamedCounterService } from 'src/app/services/rest/named-counter.service'
import { PageHeaderComponent } from '../../../../common/page-header/page-header.component'
import { NamedCounterListComponent } from './named-counter-list.component'

describe('NamedCounterListComponent', () => {
  let component: NamedCounterListComponent
  let fixture: ComponentFixture<NamedCounterListComponent>
  let namedCounterService: NamedCounterService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NgbPaginationModule,
        FormsModule,
        ReactiveFormsModule,
        NgxBootstrapIconsModule.pick(allIcons),
        NamedCounterListComponent,
        SortableDirective,
        PageHeaderComponent,
        IfPermissionsDirective,
      ],
      providers: [
        DatePipe,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    namedCounterService = TestBed.inject(NamedCounterService)
    jest.spyOn(namedCounterService, 'listFiltered').mockReturnValue(
      of({
        count: 2,
        all: [1, 2],
        results: [
          { id: 1, name: 'Binder A' },
          { id: 2, name: 'Binder B' },
        ],
      })
    )
    fixture = TestBed.createComponent(NamedCounterListComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  // Core tests are included in management-list.component.spec.ts

  it('should use correct delete message', () => {
    expect(component.getDeleteMessage({ id: 1, name: 'Binder A' })).toEqual(
      'Do you really want to delete the named counter "Binder A"?'
    )
  })
})
