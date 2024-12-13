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
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { DocumentTypeListComponent } from './document-type-list.component'

describe('DocumentTypeListComponent', () => {
  let component: DocumentTypeListComponent
  let fixture: ComponentFixture<DocumentTypeListComponent>
  let documentTypeService: DocumentTypeService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        DocumentTypeListComponent,
        SortableDirective,
        PageHeaderComponent,
        IfPermissionsDirective,
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

    documentTypeService = TestBed.inject(DocumentTypeService)
    jest.spyOn(documentTypeService, 'listFiltered').mockReturnValue(
      of({
        count: 3,
        all: [1, 2, 3],
        results: [
          {
            id: 1,
            name: 'DocumentType1',
          },
          {
            id: 2,
            name: 'DocumentType2',
          },
          {
            id: 3,
            name: 'DocumentType3',
          },
        ],
      })
    )
    fixture = TestBed.createComponent(DocumentTypeListComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  // Tests are included in management-list.component.spec.ts

  it('should use correct delete message', () => {
    expect(
      component.getDeleteMessage({ id: 1, name: 'DocumentType1' })
    ).toEqual('Do you really want to delete the document type "DocumentType1"?')
  })
})
