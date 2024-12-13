import { DatePipe } from '@angular/common'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of } from 'rxjs'
import { StoragePath } from 'src/app/data/storage-path'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SortableDirective } from 'src/app/directives/sortable.directive'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { StoragePathListComponent } from './storage-path-list.component'

describe('StoragePathListComponent', () => {
  let component: StoragePathListComponent
  let fixture: ComponentFixture<StoragePathListComponent>
  let storagePathService: StoragePathService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        StoragePathListComponent,
        SortableDirective,
        PageHeaderComponent,
        IfPermissionsDirective,
        SafeHtmlPipe,
      ],
      imports: [
        NgbPaginationModule,
        FormsModule,
        ReactiveFormsModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        DatePipe,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    storagePathService = TestBed.inject(StoragePathService)
    jest.spyOn(storagePathService, 'listFiltered').mockReturnValue(
      of({
        count: 3,
        all: [1, 2, 3],
        results: [
          {
            id: 1,
            name: 'StoragePath1',
          },
          {
            id: 2,
            name: 'StoragePath2',
          },
          {
            id: 3,
            name: 'StoragePath3',
          },
        ],
      })
    )
    fixture = TestBed.createComponent(StoragePathListComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  // Tests are included in management-list.component.spec.ts

  it('should use correct delete message', () => {
    expect(component.getDeleteMessage({ id: 1, name: 'StoragePath1' })).toEqual(
      'Do you really want to delete the storage path "StoragePath1"?'
    )
  })

  it('should truncate path if necessary', () => {
    const path: StoragePath = {
      id: 1,
      name: 'StoragePath1',
      path: 'a'.repeat(100),
    }
    expect(component.extraColumns[0].valueFn(path)).toEqual(
      `<code>${'a'.repeat(49)}...</code>`
    )
  })
})
