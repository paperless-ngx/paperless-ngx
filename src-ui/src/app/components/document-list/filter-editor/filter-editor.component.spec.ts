import { DatePipe } from '@angular/common'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import {
  ComponentFixture,
  fakeAsync,
  TestBed,
  tick,
} from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import {
  NgbDropdownModule,
  NgbDatepickerModule,
  NgbDropdownItem,
  NgbTypeaheadModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgSelectComponent, NgSelectModule } from '@ng-select/ng-select'
import { of, throwError } from 'rxjs'
import {
  FILTER_TITLE,
  FILTER_TITLE_CONTENT,
  FILTER_ASN,
  FILTER_ASN_ISNULL,
  FILTER_ASN_GT,
  FILTER_ASN_LT,
  FILTER_FULLTEXT_QUERY,
  FILTER_FULLTEXT_MORELIKE,
  FILTER_CREATED_AFTER,
  FILTER_CREATED_BEFORE,
  FILTER_ADDED_AFTER,
  FILTER_ADDED_BEFORE,
  FILTER_HAS_TAGS_ALL,
  FILTER_HAS_TAGS_ANY,
  FILTER_HAS_ANY_TAG,
  FILTER_DOES_NOT_HAVE_TAG,
  FILTER_CORRESPONDENT,
  FILTER_HAS_CORRESPONDENT_ANY,
  FILTER_DOES_NOT_HAVE_CORRESPONDENT,
  FILTER_DOCUMENT_TYPE,
  FILTER_HAS_DOCUMENT_TYPE_ANY,
  FILTER_DOES_NOT_HAVE_DOCUMENT_TYPE,
  FILTER_STORAGE_PATH,
  FILTER_HAS_STORAGE_PATH_ANY,
  FILTER_DOES_NOT_HAVE_STORAGE_PATH,
  FILTER_OWNER,
  FILTER_OWNER_ANY,
  FILTER_OWNER_DOES_NOT_INCLUDE,
  FILTER_OWNER_ISNULL,
  FILTER_CUSTOM_FIELDS_TEXT,
  FILTER_SHARED_BY_USER,
  FILTER_HAS_CUSTOM_FIELDS_ANY,
  FILTER_HAS_ANY_CUSTOM_FIELDS,
  FILTER_DOES_NOT_HAVE_CUSTOM_FIELDS,
  FILTER_HAS_CUSTOM_FIELDS_ALL,
  FILTER_CUSTOM_FIELDS_QUERY,
} from 'src/app/data/filter-rule-type'
import { Correspondent } from 'src/app/data/correspondent'
import { DocumentType } from 'src/app/data/document-type'
import { StoragePath } from 'src/app/data/storage-path'
import { Tag } from 'src/app/data/tag'
import { User } from 'src/app/data/user'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { FilterPipe } from 'src/app/pipes/filter.pipe'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { TagService } from 'src/app/services/rest/tag.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ClearableBadgeComponent } from '../../common/clearable-badge/clearable-badge.component'
import { DatesDropdownComponent } from '../../common/dates-dropdown/dates-dropdown.component'
import {
  FilterableDropdownComponent,
  LogicalOperator,
  Intersection,
} from '../../common/filterable-dropdown/filterable-dropdown.component'
import { ToggleableDropdownButtonComponent } from '../../common/filterable-dropdown/toggleable-dropdown-button/toggleable-dropdown-button.component'
import {
  PermissionsFilterDropdownComponent,
  OwnerFilterType,
} from '../../common/permissions-filter-dropdown/permissions-filter-dropdown.component'
import { FilterEditorComponent } from './filter-editor.component'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import {
  PermissionType,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { environment } from 'src/environments/environment'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { RouterModule } from '@angular/router'
import { SearchService } from 'src/app/services/rest/search.service'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { CustomFieldsQueryDropdownComponent } from '../../common/custom-fields-query-dropdown/custom-fields-query-dropdown.component'
import {
  CustomFieldQueryLogicalOperator,
  CustomFieldQueryOperator,
} from 'src/app/data/custom-field-query'
import {
  CustomFieldQueryAtom,
  CustomFieldQueryExpression,
} from 'src/app/utils/custom-field-query-element'

const tags: Tag[] = [
  {
    id: 2,
    name: 'Tag2',
  },
  {
    id: 3,
    name: 'Tag3',
  },
]

const correspondents: Correspondent[] = [
  {
    id: 12,
    name: 'Corresp12',
  },
  {
    id: 13,
    name: 'Corresp13',
  },
]

const document_types: DocumentType[] = [
  {
    id: 22,
    name: 'DocType22',
  },
  {
    id: 23,
    name: 'DocType23',
  },
]

const storage_paths: StoragePath[] = [
  {
    id: 32,
    name: 'StoragePath32',
  },
  {
    id: 33,
    name: 'StoragePath33',
  },
]

const custom_fields: CustomField[] = [
  {
    id: 42,
    data_type: CustomFieldDataType.String,
    name: 'CustomField42',
  },
  {
    id: 43,
    data_type: CustomFieldDataType.String,
    name: 'CustomField43',
  },
]

const users: User[] = [
  {
    id: 1,
    username: 'user1',
  },
]

describe('FilterEditorComponent', () => {
  let component: FilterEditorComponent
  let fixture: ComponentFixture<FilterEditorComponent>
  let documentService: DocumentService
  let settingsService: SettingsService
  let permissionsService: PermissionsService
  let httpTestingController: HttpTestingController
  let searchService: SearchService

  beforeEach(fakeAsync(() => {
    TestBed.configureTestingModule({
      declarations: [
        FilterEditorComponent,
        FilterableDropdownComponent,
        PermissionsFilterDropdownComponent,
        FilterPipe,
        IfPermissionsDirective,
        ClearableBadgeComponent,
        ToggleableDropdownButtonComponent,
        DatesDropdownComponent,
        CustomDatePipe,
        CustomFieldsQueryDropdownComponent,
      ],
      imports: [
        RouterModule,
        NgbDropdownModule,
        FormsModule,
        ReactiveFormsModule,
        NgbDatepickerModule,
        NgxBootstrapIconsModule.pick(allIcons),
        NgbTypeaheadModule,
        NgSelectModule,
      ],
      providers: [
        FilterPipe,
        CustomDatePipe,
        DatePipe,
        {
          provide: TagService,
          useValue: {
            listAll: () => of({ results: tags }),
          },
        },
        {
          provide: CorrespondentService,
          useValue: {
            listAll: () => of({ results: correspondents }),
          },
        },
        {
          provide: DocumentTypeService,
          useValue: {
            listAll: () => of({ results: document_types }),
          },
        },
        {
          provide: StoragePathService,
          useValue: {
            listAll: () => of({ results: storage_paths }),
          },
        },
        {
          provide: CustomFieldsService,
          useValue: {
            listAll: () => of({ results: custom_fields }),
          },
        },
        {
          provide: UserService,
          useValue: {
            listAll: () => of({ results: users }),
          },
        },
        SettingsService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    documentService = TestBed.inject(DocumentService)
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser = users[0]
    permissionsService = TestBed.inject(PermissionsService)
    searchService = TestBed.inject(SearchService)
    jest
      .spyOn(permissionsService, 'currentUserCan')
      .mockImplementation((action, type) => {
        // a little hack-ish, permissions filter dropdown causes reactive forms issue due to ng-select
        // trying to apply formControlName
        return type !== PermissionType.User
      })
    httpTestingController = TestBed.inject(HttpTestingController)
    fixture = TestBed.createComponent(FilterEditorComponent)
    component = fixture.componentInstance
    component.filterRules = []
    fixture.detectChanges()
    tick()
  }))

  it('should not attempt to retrieve objects if user does not have permissions', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReset()
    jest
      .spyOn(permissionsService, 'currentUserCan')
      .mockImplementation((action, type) => false)
    component.ngOnInit()
    httpTestingController.expectNone(`${environment.apiBaseUrl}documents/tags/`)
    httpTestingController.expectNone(
      `${environment.apiBaseUrl}documents/correspondents/`
    )
    httpTestingController.expectNone(
      `${environment.apiBaseUrl}documents/document_types/`
    )
    httpTestingController.expectNone(
      `${environment.apiBaseUrl}documents/storage_paths/`
    )
  })

  // SET filterRules

  it('should ingest text filter rules for doc title', fakeAsync(() => {
    expect(component.textFilter).toEqual(null)
    component.filterRules = [
      {
        rule_type: FILTER_TITLE,
        value: 'foo',
      },
    ]
    expect(component.textFilter).toEqual('foo')
    expect(component.textFilterTarget).toEqual('title') // TEXT_FILTER_TARGET_TITLE
  }))

  it('should ingest text filter rules for doc title + content', fakeAsync(() => {
    expect(component.textFilter).toEqual(null)
    component.filterRules = [
      {
        rule_type: FILTER_TITLE_CONTENT,
        value: 'foo',
      },
    ]
    expect(component.textFilter).toEqual('foo')
    expect(component.textFilterTarget).toEqual('title-content') // TEXT_FILTER_TARGET_TITLE_CONTENT
  }))

  it('should ingest text filter rules for doc asn', fakeAsync(() => {
    expect(component.textFilter).toEqual(null)
    component.filterRules = [
      {
        rule_type: FILTER_ASN,
        value: 'foo',
      },
    ]
    expect(component.textFilter).toEqual('foo')
    expect(component.textFilterTarget).toEqual('asn') // TEXT_FILTER_TARGET_ASN
  }))

  it('should ingest text filter rules for custom fields', fakeAsync(() => {
    expect(component.textFilter).toEqual(null)
    component.filterRules = [
      {
        rule_type: FILTER_CUSTOM_FIELDS_TEXT,
        value: 'foo',
      },
    ]
    expect(component.textFilter).toEqual('foo')
    expect(component.textFilterTarget).toEqual('custom-fields') // TEXT_FILTER_TARGET_CUSTOM_FIELDS
  }))

  it('should ingest text filter rules for doc asn is null', fakeAsync(() => {
    expect(component.textFilterTarget).toEqual('title-content')
    expect(component.textFilterModifier).toEqual('equals') // TEXT_FILTER_MODIFIER_EQUALS
    component.filterRules = [
      {
        rule_type: FILTER_ASN_ISNULL,
        value: 'true',
      },
    ]
    expect(component.textFilterTarget).toEqual('asn') // TEXT_FILTER_TARGET_ASN
    expect(component.textFilterModifier).toEqual('is null') // TEXT_FILTER_MODIFIER_NULL
  }))

  it('should ingest text filter rules for doc asn is not null', fakeAsync(() => {
    expect(component.textFilterTarget).toEqual('title-content')
    expect(component.textFilterModifier).toEqual('equals') // TEXT_FILTER_MODIFIER_EQUALS
    component.filterRules = [
      {
        rule_type: FILTER_ASN_ISNULL,
        value: 'false',
      },
    ]
    expect(component.textFilterTarget).toEqual('asn') // TEXT_FILTER_TARGET_ASN
    expect(component.textFilterModifier).toEqual('not null') // TEXT_FILTER_MODIFIER_NOTNULL
  }))

  it('should ingest text filter rules for doc asn greater than', fakeAsync(() => {
    expect(component.textFilterTarget).toEqual('title-content')
    expect(component.textFilterModifier).toEqual('equals') // TEXT_FILTER_MODIFIER_EQUALS
    component.filterRules = [
      {
        rule_type: FILTER_ASN_GT,
        value: '0',
      },
    ]
    expect(component.textFilterTarget).toEqual('asn') // TEXT_FILTER_TARGET_ASN
    expect(component.textFilterModifier).toEqual('greater') // TEXT_FILTER_MODIFIER_GT
  }))

  it('should ingest text filter rules for doc asn less than', fakeAsync(() => {
    expect(component.textFilterTarget).toEqual('title-content')
    expect(component.textFilterModifier).toEqual('equals') // TEXT_FILTER_MODIFIER_EQUALS
    component.filterRules = [
      {
        rule_type: FILTER_ASN_LT,
        value: '1000000',
      },
    ]
    expect(component.textFilterTarget).toEqual('asn') // TEXT_FILTER_TARGET_ASN
    expect(component.textFilterModifier).toEqual('less') // TEXT_FILTER_MODIFIER_LT
  }))

  it('should ingest text filter rules for fulltext query', fakeAsync(() => {
    expect(component.textFilter).toEqual(null)
    component.filterRules = [
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: 'foo,bar',
      },
    ]
    expect(component.textFilter).toEqual('foo,bar')
    expect(component.textFilterTarget).toEqual('fulltext-query') // TEXT_FILTER_TARGET_FULLTEXT_QUERY
  }))

  it('should ingest text filter rules for fulltext query that include date created', fakeAsync(() => {
    expect(component.dateCreatedRelativeDate).toBeNull()
    component.filterRules = [
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: 'created:[-1 week to now]',
      },
    ]
    expect(component.dateCreatedRelativeDate).toEqual(0) // RELATIVE_DATE_QUERYSTRINGS['-1 week to now']
    expect(component.textFilter).toBeNull()
  }))

  it('should ingest text filter rules for fulltext query that include date added', fakeAsync(() => {
    expect(component.dateAddedRelativeDate).toBeNull()
    component.filterRules = [
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: 'added:[-1 week to now]',
      },
    ]
    expect(component.dateAddedRelativeDate).toEqual(0) // RELATIVE_DATE_QUERYSTRINGS['-1 week to now']
    expect(component.textFilter).toBeNull()
  }))

  it('should ingest text filter content with relative dates that are not in quick list', fakeAsync(() => {
    expect(component.dateAddedRelativeDate).toBeNull()
    component.filterRules = [
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: 'added:[-2 week to now]',
      },
    ]
    expect(component.dateAddedRelativeDate).toBeNull()
    expect(component.textFilter).toEqual('added:[-2 week to now]')

    expect(component.dateCreatedRelativeDate).toBeNull()
    component.filterRules = [
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: 'created:[-2 week to now]',
      },
    ]
    expect(component.dateCreatedRelativeDate).toBeNull()
    expect(component.textFilter).toEqual('created:[-2 week to now]')
  }))

  it('should ingest text filter rules for more like', fakeAsync(() => {
    const moreLikeSpy = jest.spyOn(documentService, 'get')
    moreLikeSpy.mockReturnValue(of({ id: 1, title: 'Foo Bar' }))
    expect(component.textFilter).toEqual(null)
    component.filterRules = [
      {
        rule_type: FILTER_FULLTEXT_MORELIKE,
        value: '1',
      },
    ]
    expect(component.textFilterTarget).toEqual('fulltext-morelike') // TEXT_FILTER_TARGET_FULLTEXT_MORELIKE
    expect(moreLikeSpy).toHaveBeenCalledWith(1)
    expect(component.textFilter).toEqual('Foo Bar')
    // we have to do this here because it can't be done by user input
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_FULLTEXT_MORELIKE,
        value: '1',
      },
    ])
  }))

  it('should ingest filter rules for date created after', fakeAsync(() => {
    expect(component.dateCreatedAfter).toBeNull()
    component.filterRules = [
      {
        rule_type: FILTER_CREATED_AFTER,
        value: '2023-05-14',
      },
    ]
    expect(component.dateCreatedAfter).toEqual('2023-05-14')
  }))

  it('should ingest filter rules for date created before', fakeAsync(() => {
    expect(component.dateCreatedBefore).toBeNull()
    component.filterRules = [
      {
        rule_type: FILTER_CREATED_BEFORE,
        value: '2023-05-14',
      },
    ]
    expect(component.dateCreatedBefore).toEqual('2023-05-14')
  }))

  it('should ingest filter rules for date added after', fakeAsync(() => {
    expect(component.dateAddedAfter).toBeNull()
    component.filterRules = [
      {
        rule_type: FILTER_ADDED_AFTER,
        value: '2023-05-14',
      },
    ]
    expect(component.dateAddedAfter).toEqual('2023-05-14')
  }))

  it('should ingest filter rules for date added before', fakeAsync(() => {
    expect(component.dateAddedBefore).toBeNull()
    component.filterRules = [
      {
        rule_type: FILTER_ADDED_BEFORE,
        value: '2023-05-14',
      },
    ]
    expect(component.dateAddedBefore).toEqual('2023-05-14')
  }))

  it('should ingest filter rules for has all tags', fakeAsync(() => {
    expect(component.tagSelectionModel.getSelectedItems()).toHaveLength(0)
    component.filterRules = [
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: '2',
      },
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: '3',
      },
    ]
    expect(component.tagSelectionModel.logicalOperator).toEqual(
      LogicalOperator.And
    )
    expect(component.tagSelectionModel.getSelectedItems()).toEqual(tags)
    // coverage
    component.filterRules = [
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: null,
      },
    ]
    component.toggleTag(2) // coverage
  }))

  it('should ingest filter rules for has any tags', fakeAsync(() => {
    expect(component.tagSelectionModel.getSelectedItems()).toHaveLength(0)
    component.filterRules = [
      {
        rule_type: FILTER_HAS_TAGS_ANY,
        value: '2',
      },
      {
        rule_type: FILTER_HAS_TAGS_ANY,
        value: '3',
      },
    ]
    expect(component.tagSelectionModel.logicalOperator).toEqual(
      LogicalOperator.Or
    )
    expect(component.tagSelectionModel.getSelectedItems()).toEqual(tags)
    // coverage
    component.filterRules = [
      {
        rule_type: FILTER_HAS_TAGS_ANY,
        value: null,
      },
    ]
  }))

  it('should ingest filter rules for has any tag', fakeAsync(() => {
    expect(component.tagSelectionModel.getSelectedItems()).toHaveLength(0)
    component.filterRules = [
      {
        rule_type: FILTER_HAS_ANY_TAG,
        value: '1',
      },
    ]
    expect(component.tagSelectionModel.getSelectedItems()).toHaveLength(1)
    expect(component.tagSelectionModel.get(null)).toBeTruthy()
  }))

  it('should ingest filter rules for exclude tag(s)', fakeAsync(() => {
    expect(component.tagSelectionModel.getExcludedItems()).toHaveLength(0)
    component.filterRules = [
      {
        rule_type: FILTER_DOES_NOT_HAVE_TAG,
        value: '2',
      },
      {
        rule_type: FILTER_DOES_NOT_HAVE_TAG,
        value: '3',
      },
    ]
    expect(component.tagSelectionModel.logicalOperator).toEqual(
      LogicalOperator.And
    )
    expect(component.tagSelectionModel.getExcludedItems()).toEqual(tags)
    // coverage
    component.filterRules = [
      {
        rule_type: FILTER_DOES_NOT_HAVE_TAG,
        value: null,
      },
    ]
  }))

  it('should ingest filter rules for has correspondent', fakeAsync(() => {
    expect(
      component.correspondentSelectionModel.getSelectedItems()
    ).toHaveLength(0)
    component.filterRules = [
      {
        rule_type: FILTER_CORRESPONDENT,
        value: '12',
      },
    ]
    expect(component.correspondentSelectionModel.logicalOperator).toEqual(
      LogicalOperator.Or
    )
    expect(component.correspondentSelectionModel.intersection).toEqual(
      Intersection.Include
    )
    expect(component.correspondentSelectionModel.getSelectedItems()).toEqual([
      correspondents[0],
    ])
    component.toggleCorrespondent(12) // coverage
  }))

  it('should ingest filter rules for has any of correspondents', fakeAsync(() => {
    expect(
      component.correspondentSelectionModel.getSelectedItems()
    ).toHaveLength(0)
    component.filterRules = [
      {
        rule_type: FILTER_HAS_CORRESPONDENT_ANY,
        value: '12',
      },
      {
        rule_type: FILTER_HAS_CORRESPONDENT_ANY,
        value: '13',
      },
    ]
    expect(component.correspondentSelectionModel.logicalOperator).toEqual(
      LogicalOperator.Or
    )
    expect(component.correspondentSelectionModel.intersection).toEqual(
      Intersection.Include
    )
    expect(component.correspondentSelectionModel.getSelectedItems()).toEqual(
      correspondents
    )
    // coverage
    component.filterRules = [
      {
        rule_type: FILTER_HAS_CORRESPONDENT_ANY,
        value: null,
      },
    ]
  }))

  it('should ingest filter rules for does not have any of correspondents', fakeAsync(() => {
    expect(
      component.correspondentSelectionModel.getExcludedItems()
    ).toHaveLength(0)
    component.filterRules = [
      {
        rule_type: FILTER_DOES_NOT_HAVE_CORRESPONDENT,
        value: '12',
      },
      {
        rule_type: FILTER_DOES_NOT_HAVE_CORRESPONDENT,
        value: '13',
      },
    ]
    expect(component.correspondentSelectionModel.intersection).toEqual(
      Intersection.Exclude
    )
    expect(component.correspondentSelectionModel.getExcludedItems()).toEqual(
      correspondents
    )
    // coverage
    component.filterRules = [
      {
        rule_type: FILTER_DOES_NOT_HAVE_CORRESPONDENT,
        value: null,
      },
    ]
  }))

  it('should ingest filter rules for has document type', fakeAsync(() => {
    expect(
      component.documentTypeSelectionModel.getSelectedItems()
    ).toHaveLength(0)
    component.filterRules = [
      {
        rule_type: FILTER_DOCUMENT_TYPE,
        value: '22',
      },
    ]
    expect(component.documentTypeSelectionModel.logicalOperator).toEqual(
      LogicalOperator.Or
    )
    expect(component.documentTypeSelectionModel.intersection).toEqual(
      Intersection.Include
    )
    expect(component.documentTypeSelectionModel.getSelectedItems()).toEqual([
      document_types[0],
    ])
    component.toggleDocumentType(22) // coverage
  }))

  it('should ingest filter rules for has any of document types', fakeAsync(() => {
    expect(
      component.documentTypeSelectionModel.getSelectedItems()
    ).toHaveLength(0)
    component.filterRules = [
      {
        rule_type: FILTER_HAS_DOCUMENT_TYPE_ANY,
        value: '22',
      },
      {
        rule_type: FILTER_HAS_DOCUMENT_TYPE_ANY,
        value: '23',
      },
    ]
    expect(component.documentTypeSelectionModel.logicalOperator).toEqual(
      LogicalOperator.Or
    )
    expect(component.documentTypeSelectionModel.intersection).toEqual(
      Intersection.Include
    )
    expect(component.documentTypeSelectionModel.getSelectedItems()).toEqual(
      document_types
    )
    // coverage
    component.filterRules = [
      {
        rule_type: FILTER_HAS_DOCUMENT_TYPE_ANY,
        value: null,
      },
    ]
  }))

  it('should ingest filter rules for does not have any of document types', fakeAsync(() => {
    expect(
      component.documentTypeSelectionModel.getExcludedItems()
    ).toHaveLength(0)
    component.filterRules = [
      {
        rule_type: FILTER_DOES_NOT_HAVE_DOCUMENT_TYPE,
        value: '22',
      },
      {
        rule_type: FILTER_DOES_NOT_HAVE_DOCUMENT_TYPE,
        value: '23',
      },
    ]
    expect(component.documentTypeSelectionModel.intersection).toEqual(
      Intersection.Exclude
    )
    expect(component.documentTypeSelectionModel.getExcludedItems()).toEqual(
      document_types
    )
    // coverage
    component.filterRules = [
      {
        rule_type: FILTER_DOES_NOT_HAVE_DOCUMENT_TYPE,
        value: null,
      },
    ]
  }))

  it('should ingest filter rules for has storage path', fakeAsync(() => {
    expect(component.storagePathSelectionModel.getSelectedItems()).toHaveLength(
      0
    )
    component.filterRules = [
      {
        rule_type: FILTER_STORAGE_PATH,
        value: '32',
      },
    ]
    expect(component.storagePathSelectionModel.logicalOperator).toEqual(
      LogicalOperator.Or
    )
    expect(component.storagePathSelectionModel.intersection).toEqual(
      Intersection.Include
    )
    expect(component.storagePathSelectionModel.getSelectedItems()).toEqual([
      storage_paths[0],
    ])
    component.toggleStoragePath(32) // coverage
  }))

  it('should ingest filter rules for has any of storage paths', fakeAsync(() => {
    expect(component.storagePathSelectionModel.getSelectedItems()).toHaveLength(
      0
    )
    component.filterRules = [
      {
        rule_type: FILTER_HAS_STORAGE_PATH_ANY,
        value: '32',
      },
      {
        rule_type: FILTER_HAS_STORAGE_PATH_ANY,
        value: '33',
      },
    ]
    expect(component.storagePathSelectionModel.logicalOperator).toEqual(
      LogicalOperator.Or
    )
    expect(component.storagePathSelectionModel.intersection).toEqual(
      Intersection.Include
    )
    expect(component.storagePathSelectionModel.getSelectedItems()).toEqual(
      storage_paths
    )
    // coverage
    component.filterRules = [
      {
        rule_type: FILTER_HAS_STORAGE_PATH_ANY,
        value: null,
      },
    ]
  }))

  it('should ingest filter rules for does not have any of storage paths', fakeAsync(() => {
    expect(component.storagePathSelectionModel.getExcludedItems()).toHaveLength(
      0
    )
    component.filterRules = [
      {
        rule_type: FILTER_DOES_NOT_HAVE_STORAGE_PATH,
        value: '32',
      },
      {
        rule_type: FILTER_DOES_NOT_HAVE_STORAGE_PATH,
        value: '33',
      },
    ]
    expect(component.storagePathSelectionModel.intersection).toEqual(
      Intersection.Exclude
    )
    expect(component.storagePathSelectionModel.getExcludedItems()).toEqual(
      storage_paths
    )
    // coverage
    component.filterRules = [
      {
        rule_type: FILTER_DOES_NOT_HAVE_STORAGE_PATH,
        value: null,
      },
    ]
  }))

  it('should ingest filter rules for custom fields all', fakeAsync(() => {
    expect(component.customFieldQueriesModel.isEmpty()).toBeTruthy()
    component.filterRules = [
      {
        rule_type: FILTER_HAS_CUSTOM_FIELDS_ALL,
        value: '42,43',
      },
    ]
    expect(component.customFieldQueriesModel.queries[0].operator).toEqual(
      CustomFieldQueryLogicalOperator.And
    )
    expect(component.customFieldQueriesModel.queries[0].value.length).toEqual(2)
    expect(
      (
        component.customFieldQueriesModel.queries[0]
          .value[0] as CustomFieldQueryAtom
      ).serialize()
    ).toEqual(['42', CustomFieldQueryOperator.Exists, 'true'])
  }))

  it('should ingest filter rules for has any custom fields', fakeAsync(() => {
    expect(component.customFieldQueriesModel.isEmpty()).toBeTruthy()
    component.filterRules = [
      {
        rule_type: FILTER_HAS_CUSTOM_FIELDS_ANY,
        value: '42,43',
      },
    ]
    expect(component.customFieldQueriesModel.queries[0].operator).toEqual(
      CustomFieldQueryLogicalOperator.Or
    )
    expect(component.customFieldQueriesModel.queries[0].value.length).toEqual(2)
    expect(
      (
        component.customFieldQueriesModel.queries[0]
          .value[0] as CustomFieldQueryAtom
      ).serialize()
    ).toEqual(['42', CustomFieldQueryOperator.Exists, 'true'])
  }))

  it('should ingest filter rules for custom field queries', fakeAsync(() => {
    expect(component.customFieldQueriesModel.isEmpty()).toBeTruthy()
    component.filterRules = [
      {
        rule_type: FILTER_CUSTOM_FIELDS_QUERY,
        value: '["AND", [[42, "exists", "true"],[43, "exists", "true"]]]',
      },
    ]
    expect(component.customFieldQueriesModel.queries[0].operator).toEqual(
      CustomFieldQueryLogicalOperator.And
    )
    expect(component.customFieldQueriesModel.queries[0].value.length).toEqual(2)
    expect(
      (
        component.customFieldQueriesModel.queries[0]
          .value[0] as CustomFieldQueryAtom
      ).serialize()
    ).toEqual([42, CustomFieldQueryOperator.Exists, 'true'])

    // atom
    component.filterRules = [
      {
        rule_type: FILTER_CUSTOM_FIELDS_QUERY,
        value: '[42, "exists", "true"]',
      },
    ]
    expect(component.customFieldQueriesModel.queries[0].value.length).toEqual(1)
    expect(
      (
        component.customFieldQueriesModel.queries[0]
          .value[0] as CustomFieldQueryAtom
      ).serialize()
    ).toEqual([42, CustomFieldQueryOperator.Exists, 'true'])
  }))

  it('should ingest filter rules for owner', fakeAsync(() => {
    expect(component.permissionsSelectionModel.ownerFilter).toEqual(
      OwnerFilterType.NONE
    )
    component.filterRules = [
      {
        rule_type: FILTER_OWNER,
        value: '100',
      },
    ]
    expect(component.permissionsSelectionModel.ownerFilter).toEqual(
      OwnerFilterType.SELF
    )
    expect(component.permissionsSelectionModel.hideUnowned).toBeFalsy()
    expect(component.permissionsSelectionModel.userID).toEqual(100)
  }))

  it('should ingest filter rules for owner is others', fakeAsync(() => {
    expect(component.permissionsSelectionModel.ownerFilter).toEqual(
      OwnerFilterType.NONE
    )
    component.filterRules = [
      {
        rule_type: FILTER_OWNER_ANY,
        value: '50',
      },
    ]
    expect(component.permissionsSelectionModel.ownerFilter).toEqual(
      OwnerFilterType.OTHERS
    )
    expect(component.permissionsSelectionModel.includeUsers).toContain(50)
  }))

  it('should ingest filter rules for owner does not include others', fakeAsync(() => {
    expect(component.permissionsSelectionModel.ownerFilter).toEqual(
      OwnerFilterType.NONE
    )
    component.filterRules = [
      {
        rule_type: FILTER_OWNER_DOES_NOT_INCLUDE,
        value: '50',
      },
    ]
    expect(component.permissionsSelectionModel.ownerFilter).toEqual(
      OwnerFilterType.NOT_SELF
    )
    expect(component.permissionsSelectionModel.excludeUsers).toContain(50)
  }))

  it('should ingest filter rules for owner is null', fakeAsync(() => {
    expect(component.permissionsSelectionModel.ownerFilter).toEqual(
      OwnerFilterType.NONE
    )
    component.filterRules = [
      {
        rule_type: FILTER_OWNER_ISNULL,
        value: 'true',
      },
    ]
    expect(component.permissionsSelectionModel.ownerFilter).toEqual(
      OwnerFilterType.UNOWNED
    )
    expect(component.permissionsSelectionModel.hideUnowned).toBeFalsy()
  }))

  it('should ingest filter rules for owner is not null', fakeAsync(() => {
    component.filterRules = [
      {
        rule_type: FILTER_OWNER_ISNULL,
        value: 'false',
      },
    ]
    expect(component.permissionsSelectionModel.hideUnowned).toBeTruthy()
    component.filterRules = [
      {
        rule_type: FILTER_OWNER_ISNULL,
        value: '0',
      },
    ]
    expect(component.permissionsSelectionModel.hideUnowned).toBeTruthy()
  }))

  it('should ingest filter rules for shared by me', fakeAsync(() => {
    component.filterRules = [
      {
        rule_type: FILTER_SHARED_BY_USER,
        value: '2',
      },
    ]
    expect(component.permissionsSelectionModel.userID).toEqual(2)
  }))

  // GET filterRules

  it('should convert user input to correct filter rules on text field search title + content', fakeAsync(() => {
    component.textFilterInput.nativeElement.value = 'foo'
    component.textFilterInput.nativeElement.dispatchEvent(new Event('input'))
    fixture.detectChanges()
    tick(400) // debounce time
    expect(component.textFilter).toEqual('foo')
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_TITLE_CONTENT,
        value: 'foo',
      },
    ])
  }))

  it('should convert user input to correct filter rules on text field search title only', fakeAsync(() => {
    component.textFilterInput.nativeElement.value = 'foo'
    component.textFilterInput.nativeElement.dispatchEvent(new Event('input'))
    const textFieldTargetDropdown = fixture.debugElement.query(
      By.directive(NgbDropdownItem)
    )
    textFieldTargetDropdown.triggerEventHandler('click') // TEXT_FILTER_TARGET_TITLE
    fixture.detectChanges()
    tick(400) // debounce time
    expect(component.textFilter).toEqual('foo')
    expect(component.textFilterTarget).toEqual('title')
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_TITLE,
        value: 'foo',
      },
    ])
  }))

  it('should convert user input to correct filter rules on text field search equals asn', fakeAsync(() => {
    component.textFilterInput.nativeElement.value = '1234'
    component.textFilterInput.nativeElement.dispatchEvent(new Event('input'))
    const textFieldTargetDropdown = fixture.debugElement.queryAll(
      By.directive(NgbDropdownItem)
    )[2]
    textFieldTargetDropdown.triggerEventHandler('click') // TEXT_FILTER_TARGET_ASN
    fixture.detectChanges()
    tick(400) // debounce time
    expect(component.textFilterTarget).toEqual('asn')
    expect(component.textFilterModifier).toEqual('equals')
    expect(component.textFilter).toEqual('1234')
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_ASN,
        value: '1234',
      },
    ])
  }))

  it('should convert user input to correct filter rules on text field search greater than asn', fakeAsync(() => {
    component.textFilterInput.nativeElement.value = '123'
    component.textFilterInput.nativeElement.dispatchEvent(new Event('input'))
    const textFieldTargetDropdown = fixture.debugElement.queryAll(
      By.directive(NgbDropdownItem)
    )[2]
    textFieldTargetDropdown.triggerEventHandler('click') // TEXT_FILTER_TARGET_ASN
    fixture.detectChanges()
    tick(400) // debounce time
    const textFieldModifierSelect = fixture.debugElement.query(By.css('select'))
    textFieldModifierSelect.nativeElement.value = 'greater' // TEXT_FILTER_MODIFIER_GT
    textFieldModifierSelect.nativeElement.dispatchEvent(new Event('change'))
    fixture.detectChanges()
    expect(component.textFilterTarget).toEqual('asn')
    expect(component.textFilterModifier).toEqual('greater')
    expect(component.textFilter).toEqual('123')
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_ASN_GT,
        value: '123',
      },
    ])
  }))

  it('should convert user input to correct filter rules on text field search less than asn', fakeAsync(() => {
    component.textFilterInput.nativeElement.value = '999'
    component.textFilterInput.nativeElement.dispatchEvent(new Event('input'))
    const textFieldTargetDropdown = fixture.debugElement.queryAll(
      By.directive(NgbDropdownItem)
    )[2]
    textFieldTargetDropdown.triggerEventHandler('click') // TEXT_FILTER_TARGET_ASN
    fixture.detectChanges()
    tick(400) // debounce time
    const textFieldModifierSelect = fixture.debugElement.query(By.css('select'))
    textFieldModifierSelect.nativeElement.value = 'less' // TEXT_FILTER_MODIFIER_LT
    textFieldModifierSelect.nativeElement.dispatchEvent(new Event('change'))
    fixture.detectChanges()
    expect(component.textFilterTarget).toEqual('asn')
    expect(component.textFilterModifier).toEqual('less')
    expect(component.textFilter).toEqual('999')
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_ASN_LT,
        value: '999',
      },
    ])
  }))

  it('should convert user input to correct filter rules on asn is null', fakeAsync(() => {
    const textFieldTargetDropdown = fixture.debugElement.queryAll(
      By.directive(NgbDropdownItem)
    )[2]
    textFieldTargetDropdown.triggerEventHandler('click') // TEXT_FILTER_TARGET_ASN
    fixture.detectChanges()
    const textFieldModifierSelect = fixture.debugElement.query(By.css('select'))
    textFieldModifierSelect.nativeElement.value = 'is null' // TEXT_FILTER_MODIFIER_LT
    textFieldModifierSelect.nativeElement.dispatchEvent(new Event('change'))
    fixture.detectChanges()
    expect(component.textFilterTarget).toEqual('asn')
    expect(component.textFilterModifier).toEqual('is null')
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_ASN_ISNULL,
        value: 'true',
      },
    ])
  }))

  it('should convert user input to correct filter rules on asn is not null', fakeAsync(() => {
    const textFieldTargetDropdown = fixture.debugElement.queryAll(
      By.directive(NgbDropdownItem)
    )[2]
    textFieldTargetDropdown.triggerEventHandler('click') // TEXT_FILTER_TARGET_ASN
    fixture.detectChanges()
    const textFieldModifierSelect = fixture.debugElement.query(By.css('select'))
    textFieldModifierSelect.nativeElement.value = 'not null' // TEXT_FILTER_MODIFIER_LT
    textFieldModifierSelect.nativeElement.dispatchEvent(new Event('change'))
    fixture.detectChanges()
    expect(component.textFilterTarget).toEqual('asn')
    expect(component.textFilterModifier).toEqual('not null')
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_ASN_ISNULL,
        value: 'false',
      },
    ])
  }))

  it('should convert user input to correct filter rules on custom fields query', fakeAsync(() => {
    component.textFilterInput.nativeElement.value = 'foo'
    component.textFilterInput.nativeElement.dispatchEvent(new Event('input'))
    const textFieldTargetDropdown = fixture.debugElement.queryAll(
      By.directive(NgbDropdownItem)
    )[3]
    textFieldTargetDropdown.triggerEventHandler('click') // TEXT_FILTER_TARGET_CUSTOM_FIELDS
    fixture.detectChanges()
    tick(400)
    expect(component.textFilterTarget).toEqual('custom-fields')
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_CUSTOM_FIELDS_TEXT,
        value: 'foo',
      },
    ])
  }))

  it('should convert user input to correct filter rules on full text query', fakeAsync(() => {
    component.textFilterInput.nativeElement.value = 'foo'
    component.textFilterInput.nativeElement.dispatchEvent(new Event('input'))
    const textFieldTargetDropdown = fixture.debugElement.queryAll(
      By.directive(NgbDropdownItem)
    )[4]
    textFieldTargetDropdown.triggerEventHandler('click') // TEXT_FILTER_TARGET_ASN
    fixture.detectChanges()
    tick(400)
    expect(component.textFilterTarget).toEqual('fulltext-query')
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: 'foo',
      },
    ])
  }))

  it('should convert user input to correct filter rules on tag select not assigned', fakeAsync(() => {
    const tagsFilterableDropdown = fixture.debugElement.queryAll(
      By.directive(FilterableDropdownComponent)
    )[0]
    tagsFilterableDropdown.triggerEventHandler('opened')
    const tagButton = tagsFilterableDropdown.queryAll(
      By.directive(ToggleableDropdownButtonComponent)
    )[0]
    tagButton.triggerEventHandler('toggled')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_HAS_ANY_TAG,
        value: 'false',
      },
    ])
  }))

  it('should convert user input to correct filter rules on tag selections', fakeAsync(() => {
    const tagsFilterableDropdown = fixture.debugElement.queryAll(
      By.directive(FilterableDropdownComponent)
    )[0] // Tags dropdown
    tagsFilterableDropdown.triggerEventHandler('opened')
    const tagButtons = tagsFilterableDropdown.queryAll(
      By.directive(ToggleableDropdownButtonComponent)
    )
    tagButtons[1].triggerEventHandler('toggled')
    tagButtons[2].triggerEventHandler('toggled')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: tags[0].id.toString(),
      },
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: tags[1].id.toString(),
      },
    ])
    const toggleOperatorButtons = tagsFilterableDropdown.queryAll(
      By.css('input[type=radio]')
    )
    toggleOperatorButtons[1].nativeElement.checked = true
    toggleOperatorButtons[1].triggerEventHandler('change')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_HAS_TAGS_ANY,
        value: tags[0].id.toString(),
      },
      {
        rule_type: FILTER_HAS_TAGS_ANY,
        value: tags[1].id.toString(),
      },
    ])
    tagButtons[2].triggerEventHandler('exclude')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: tags[0].id.toString(),
      },
      {
        rule_type: FILTER_DOES_NOT_HAVE_TAG,
        value: tags[1].id.toString(),
      },
    ])
  }))

  it('should convert user input to correct filter rules on correspondent selections', fakeAsync(() => {
    const correspondentsFilterableDropdown = fixture.debugElement.queryAll(
      By.directive(FilterableDropdownComponent)
    )[1] // Corresp dropdown
    correspondentsFilterableDropdown.triggerEventHandler('opened')
    const correspondentButtons = correspondentsFilterableDropdown.queryAll(
      By.directive(ToggleableDropdownButtonComponent)
    )
    correspondentButtons[1].triggerEventHandler('toggled')
    correspondentButtons[2].triggerEventHandler('toggled')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_HAS_CORRESPONDENT_ANY,
        value: correspondents[0].id.toString(),
      },
      {
        rule_type: FILTER_HAS_CORRESPONDENT_ANY,
        value: correspondents[1].id.toString(),
      },
    ])
    const toggleIntersectionButtons = correspondentsFilterableDropdown.queryAll(
      By.css('input[type=radio]')
    )
    toggleIntersectionButtons[1].nativeElement.checked = true
    toggleIntersectionButtons[1].triggerEventHandler('change')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_DOES_NOT_HAVE_CORRESPONDENT,
        value: correspondents[0].id.toString(),
      },
      {
        rule_type: FILTER_DOES_NOT_HAVE_CORRESPONDENT,
        value: correspondents[1].id.toString(),
      },
    ])
  }))

  it('should convert user input to correct filter rules on correspondent select not assigned', fakeAsync(() => {
    const correspondentsFilterableDropdown = fixture.debugElement.queryAll(
      By.directive(FilterableDropdownComponent)
    )[1]
    correspondentsFilterableDropdown.triggerEventHandler('opened')
    const notAssignedButton = correspondentsFilterableDropdown.queryAll(
      By.directive(ToggleableDropdownButtonComponent)
    )[0]
    notAssignedButton.triggerEventHandler('toggled')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_CORRESPONDENT,
        value: null,
      },
    ])
  }))

  it('should convert user input to correct filter rules on document type selections', fakeAsync(() => {
    const documentTypesFilterableDropdown = fixture.debugElement.queryAll(
      By.directive(FilterableDropdownComponent)
    )[2] // DocType dropdown
    documentTypesFilterableDropdown.triggerEventHandler('opened')
    const documentTypeButtons = documentTypesFilterableDropdown.queryAll(
      By.directive(ToggleableDropdownButtonComponent)
    )
    documentTypeButtons[1].triggerEventHandler('toggled')
    documentTypeButtons[2].triggerEventHandler('toggled')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_HAS_DOCUMENT_TYPE_ANY,
        value: document_types[0].id.toString(),
      },
      {
        rule_type: FILTER_HAS_DOCUMENT_TYPE_ANY,
        value: document_types[1].id.toString(),
      },
    ])
    const toggleIntersectionButtons = documentTypesFilterableDropdown.queryAll(
      By.css('input[type=radio]')
    )
    toggleIntersectionButtons[1].nativeElement.checked = true
    toggleIntersectionButtons[1].triggerEventHandler('change')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_DOES_NOT_HAVE_DOCUMENT_TYPE,
        value: document_types[0].id.toString(),
      },
      {
        rule_type: FILTER_DOES_NOT_HAVE_DOCUMENT_TYPE,
        value: document_types[1].id.toString(),
      },
    ])
  }))

  it('should convert user input to correct filter rules on doc type select not assigned', fakeAsync(() => {
    const docTypesFilterableDropdown = fixture.debugElement.queryAll(
      By.directive(FilterableDropdownComponent)
    )[2]
    docTypesFilterableDropdown.triggerEventHandler('opened')
    const notAssignedButton = docTypesFilterableDropdown.queryAll(
      By.directive(ToggleableDropdownButtonComponent)
    )[0]
    notAssignedButton.triggerEventHandler('toggled')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_DOCUMENT_TYPE,
        value: null,
      },
    ])
  }))

  it('should convert user input to correct filter rules on storage path selections', fakeAsync(() => {
    const storagePathFilterableDropdown = fixture.debugElement.queryAll(
      By.directive(FilterableDropdownComponent)
    )[3] // StoragePath dropdown
    storagePathFilterableDropdown.triggerEventHandler('opened')
    const storagePathButtons = storagePathFilterableDropdown.queryAll(
      By.directive(ToggleableDropdownButtonComponent)
    )
    storagePathButtons[1].triggerEventHandler('toggled')
    storagePathButtons[2].triggerEventHandler('toggled')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_HAS_STORAGE_PATH_ANY,
        value: storage_paths[0].id.toString(),
      },
      {
        rule_type: FILTER_HAS_STORAGE_PATH_ANY,
        value: storage_paths[1].id.toString(),
      },
    ])
    const toggleIntersectionButtons = storagePathFilterableDropdown.queryAll(
      By.css('input[type=radio]')
    )
    toggleIntersectionButtons[1].nativeElement.checked = true
    toggleIntersectionButtons[1].triggerEventHandler('change')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_DOES_NOT_HAVE_STORAGE_PATH,
        value: storage_paths[0].id.toString(),
      },
      {
        rule_type: FILTER_DOES_NOT_HAVE_STORAGE_PATH,
        value: storage_paths[1].id.toString(),
      },
    ])
  }))

  it('should convert user input to correct filter rules on storage path select not assigned', fakeAsync(() => {
    const storagePathsFilterableDropdown = fixture.debugElement.queryAll(
      By.directive(FilterableDropdownComponent)
    )[3]
    storagePathsFilterableDropdown.triggerEventHandler('opened')
    const notAssignedButton = storagePathsFilterableDropdown.queryAll(
      By.directive(ToggleableDropdownButtonComponent)
    )[0]
    notAssignedButton.triggerEventHandler('toggled')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_STORAGE_PATH,
        value: null,
      },
    ])
  }))

  it('should convert user input to correct filter rules on custom field selections', fakeAsync(() => {
    const customFieldsQueryDropdown = fixture.debugElement.queryAll(
      By.directive(CustomFieldsQueryDropdownComponent)
    )[0]
    const customFieldToggleButton = customFieldsQueryDropdown.query(
      By.css('button')
    )
    customFieldToggleButton.triggerEventHandler('click')
    tick()
    fixture.detectChanges()
    const expression = component.customFieldQueriesModel
      .queries[0] as CustomFieldQueryExpression
    const atom = expression.value[0] as CustomFieldQueryAtom
    atom.field = custom_fields[0].id
    const fieldSelect: NgSelectComponent = customFieldsQueryDropdown.queryAll(
      By.directive(NgSelectComponent)
    )[0].componentInstance
    fieldSelect.open()
    const options = customFieldsQueryDropdown.queryAll(By.css('.ng-option'))
    options[0].nativeElement.click()
    expect(component.customFieldQueriesModel.queries[0].value.length).toEqual(1)
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_CUSTOM_FIELDS_QUERY,
        value: JSON.stringify([
          CustomFieldQueryLogicalOperator.Or,
          [[custom_fields[0].id, 'exists', 'true']],
        ]),
      },
    ])
  }))

  it('should convert user input to correct filter rules on date created after', fakeAsync(() => {
    const dateCreatedDropdown = fixture.debugElement.queryAll(
      By.directive(DatesDropdownComponent)
    )[0]
    const dateCreatedAfter = dateCreatedDropdown.queryAll(By.css('input'))[0]

    dateCreatedAfter.nativeElement.value = '05/14/2023'
    // dateCreatedAfter.triggerEventHandler('change')
    // TODO: why isn't ngModel triggering this on change?
    component.dateCreatedAfter = '2023-05-14'
    fixture.detectChanges()
    tick(400)
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_CREATED_AFTER,
        value: '2023-05-14',
      },
    ])
  }))

  it('should convert user input to correct filter rules on date created before', fakeAsync(() => {
    const dateCreatedDropdown = fixture.debugElement.queryAll(
      By.directive(DatesDropdownComponent)
    )[0]
    const dateCreatedBefore = dateCreatedDropdown.queryAll(By.css('input'))[1]

    dateCreatedBefore.nativeElement.value = '05/14/2023'
    // dateCreatedBefore.triggerEventHandler('change')
    // TODO: why isn't ngModel triggering this on change?
    component.dateCreatedBefore = '2023-05-14'
    fixture.detectChanges()
    tick(400)
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_CREATED_BEFORE,
        value: '2023-05-14',
      },
    ])
  }))

  it('should convert user input to correct filter rules on date created with relative date', fakeAsync(() => {
    const dateCreatedDropdown = fixture.debugElement.queryAll(
      By.directive(DatesDropdownComponent)
    )[0]
    const dateCreatedBeforeRelativeButton = dateCreatedDropdown.queryAll(
      By.css('button')
    )[1]
    dateCreatedBeforeRelativeButton.triggerEventHandler('click')
    fixture.detectChanges()
    tick(400)
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: 'created:[-1 week to now]',
      },
    ])
  }))

  it('should carry over text filtering on date created with relative date', fakeAsync(() => {
    component.textFilter = 'foo'
    const dateCreatedDropdown = fixture.debugElement.queryAll(
      By.directive(DatesDropdownComponent)
    )[0]
    const dateCreatedBeforeRelativeButton = dateCreatedDropdown.queryAll(
      By.css('button')
    )[1]
    dateCreatedBeforeRelativeButton.triggerEventHandler('click')
    fixture.detectChanges()
    tick(400)
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: 'foo,created:[-1 week to now]',
      },
    ])
  }))

  it('should leave relative dates not in quick list intact', fakeAsync(() => {
    component.textFilterInput.nativeElement.value = 'created:[-2 week to now]'
    component.textFilterInput.nativeElement.dispatchEvent(new Event('input'))
    const textFieldTargetDropdown = fixture.debugElement.queryAll(
      By.directive(NgbDropdownItem)
    )[4]
    textFieldTargetDropdown.triggerEventHandler('click')
    fixture.detectChanges()
    tick(400)
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: 'created:[-2 week to now]',
      },
    ])

    component.textFilterInput.nativeElement.value = 'added:[-2 month to now]'
    component.textFilterInput.nativeElement.dispatchEvent(new Event('input'))
    fixture.detectChanges()
    tick(400)
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: 'added:[-2 month to now]',
      },
    ])
  }))

  it('should convert user input to correct filter rules on date added after', fakeAsync(() => {
    const datesDropdown = fixture.debugElement.query(
      By.directive(DatesDropdownComponent)
    )
    const dateAddedAfter = datesDropdown.queryAll(By.css('input'))[2]

    dateAddedAfter.nativeElement.value = '05/14/2023'
    // dateAddedAfter.triggerEventHandler('change')
    // TODO: why isn't ngModel triggering this on change?
    component.dateAddedAfter = '2023-05-14'
    fixture.detectChanges()
    tick(400)
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_ADDED_AFTER,
        value: '2023-05-14',
      },
    ])
  }))

  it('should convert user input to correct filter rules on date added before', fakeAsync(() => {
    const datesDropdown = fixture.debugElement.query(
      By.directive(DatesDropdownComponent)
    )
    const dateAddedBefore = datesDropdown.queryAll(By.css('input'))[2]

    dateAddedBefore.nativeElement.value = '05/14/2023'
    // dateAddedBefore.triggerEventHandler('change')
    // TODO: why isn't ngModel triggering this on change?
    component.dateAddedBefore = '2023-05-14'
    fixture.detectChanges()
    tick(400)
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_ADDED_BEFORE,
        value: '2023-05-14',
      },
    ])
  }))

  it('should convert user input to correct filter rules on date added with relative date', fakeAsync(() => {
    const datesDropdown = fixture.debugElement.query(
      By.directive(DatesDropdownComponent)
    )
    const dateCreatedBeforeRelativeButton = datesDropdown.queryAll(
      By.css('button')
    )[1]
    dateCreatedBeforeRelativeButton.triggerEventHandler('click')
    fixture.detectChanges()
    tick(400)
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: 'created:[-1 week to now]',
      },
    ])
  }))

  it('should carry over text filtering on date added with relative date', fakeAsync(() => {
    component.textFilter = 'foo'
    const datesDropdown = fixture.debugElement.query(
      By.directive(DatesDropdownComponent)
    )
    const dateCreatedBeforeRelativeButton = datesDropdown.queryAll(
      By.css('button')
    )[1]
    dateCreatedBeforeRelativeButton.triggerEventHandler('click')
    fixture.detectChanges()
    tick(400)
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_FULLTEXT_QUERY,
        value: 'foo,created:[-1 week to now]',
      },
    ])
  }))

  it('should convert user input to correct filter on permissions select my docs', fakeAsync(() => {
    const permissionsDropdown = fixture.debugElement.query(
      By.directive(PermissionsFilterDropdownComponent)
    )
    const myDocsButton = permissionsDropdown.queryAll(By.css('button'))[2]
    myDocsButton.triggerEventHandler('click')
    fixture.detectChanges()
    tick(400)
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_OWNER,
        value: '1',
      },
    ])
  }))

  it('should convert user input to correct filter on permissions select shared with me', fakeAsync(() => {
    const permissionsDropdown = fixture.debugElement.query(
      By.directive(PermissionsFilterDropdownComponent)
    )
    const sharedWithMe = permissionsDropdown.queryAll(By.css('button'))[3]
    sharedWithMe.triggerEventHandler('click')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_OWNER_DOES_NOT_INCLUDE,
        value: '1',
      },
    ])
  }))

  it('should convert user input to correct filter on permissions select shared with me', fakeAsync(() => {
    const permissionsDropdown = fixture.debugElement.query(
      By.directive(PermissionsFilterDropdownComponent)
    )
    const sharedWithMeButton = permissionsDropdown.queryAll(By.css('button'))[3]
    sharedWithMeButton.triggerEventHandler('click')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_OWNER_DOES_NOT_INCLUDE,
        value: '1',
      },
    ])
    component.permissionsSelectionModel.excludeUsers.push(2)
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_OWNER_DOES_NOT_INCLUDE,
        value: '1,2',
      },
    ])
  }))

  it('should convert user input to correct filter on permissions select shared by me', fakeAsync(() => {
    const permissionsDropdown = fixture.debugElement.query(
      By.directive(PermissionsFilterDropdownComponent)
    )
    const unownedButton = permissionsDropdown.queryAll(By.css('button'))[4]
    unownedButton.triggerEventHandler('click')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_SHARED_BY_USER,
        value: '1',
      },
    ])
  }))

  it('should convert user input to correct filter on permissions select unowned', fakeAsync(() => {
    const permissionsDropdown = fixture.debugElement.query(
      By.directive(PermissionsFilterDropdownComponent)
    )
    const unownedButton = permissionsDropdown.queryAll(By.css('button'))[5]
    unownedButton.triggerEventHandler('click')
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_OWNER_ISNULL,
        value: 'true',
      },
    ])
  }))

  it('should convert user input to correct filter on permissions select others', fakeAsync(() => {
    const permissionsDropdown = fixture.debugElement.query(
      By.directive(PermissionsFilterDropdownComponent)
    )
    const userSelect = permissionsDropdown.query(
      By.directive(NgSelectComponent)
    )
    // TODO: mock input in code
    // userSelect.query(By.css('input')).nativeElement.value = '3'
    // userSelect.triggerEventHandler('change')
    component.permissionsSelectionModel.ownerFilter = OwnerFilterType.OTHERS
    component.permissionsSelectionModel.includeUsers.push(3)
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_OWNER_ANY,
        value: '3',
      },
    ])
  }))

  it('should convert user input to correct filter on permissions hide unowned', fakeAsync(() => {
    const permissionsDropdown = fixture.debugElement.query(
      By.directive(PermissionsFilterDropdownComponent)
    )
    const ownerToggle = permissionsDropdown.query(
      By.css('input[type=checkbox]')
    )
    ownerToggle.nativeElement.checked = true
    // ownerToggle.triggerEventHandler('change')
    // TODO: ngModel isn't doing this here
    component.permissionsSelectionModel.hideUnowned = true
    fixture.detectChanges()
    expect(component.filterRules).toEqual([
      {
        rule_type: FILTER_OWNER_ISNULL,
        value: 'false',
      },
    ])
  }))

  // The rest

  it('should support setting selection data', () => {
    component.selectionData = null
    component.selectionData = {
      selected_storage_paths: [
        { id: 2, document_count: 1 },
        { id: 3, document_count: 0 },
      ],
      selected_correspondents: [
        { id: 12, document_count: 1 },
        { id: 13, document_count: 0 },
      ],
      selected_tags: [
        { id: 22, document_count: 1 },
        { id: 23, document_count: 0 },
      ],
      selected_document_types: [
        { id: 32, document_count: 1 },
        { id: 33, document_count: 0 },
      ],
      selected_custom_fields: [
        { id: 42, document_count: 1 },
        { id: 43, document_count: 0 },
      ],
    }
  })

  it('should generate filter names', () => {
    component.filterRules = [
      {
        rule_type: FILTER_HAS_CORRESPONDENT_ANY,
        value: '12',
      },
    ]
    expect(component.generateFilterName()).toEqual(
      `Correspondent: ${correspondents[0].name}`
    )

    component.filterRules = [
      {
        rule_type: FILTER_CORRESPONDENT,
        value: null,
      },
    ]
    expect(component.generateFilterName()).toEqual('Without correspondent')

    component.filterRules = [
      {
        rule_type: FILTER_HAS_DOCUMENT_TYPE_ANY,
        value: '22',
      },
    ]
    expect(component.generateFilterName()).toEqual(
      `Document type: ${document_types[0].name}`
    )

    component.filterRules = [
      {
        rule_type: FILTER_DOCUMENT_TYPE,
        value: null,
      },
    ]
    expect(component.generateFilterName()).toEqual('Without document type')

    component.filterRules = [
      {
        rule_type: FILTER_HAS_STORAGE_PATH_ANY,
        value: '32',
      },
    ]
    expect(component.generateFilterName()).toEqual(
      `Storage path: ${storage_paths[0].name}`
    )

    component.filterRules = [
      {
        rule_type: FILTER_STORAGE_PATH,
        value: null,
      },
    ]
    expect(component.generateFilterName()).toEqual('Without storage path')

    component.filterRules = [
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: '2',
      },
    ]
    expect(component.generateFilterName()).toEqual(`Tag: ${tags[0].name}`)

    component.filterRules = [
      {
        rule_type: FILTER_HAS_ANY_TAG,
        value: 'false',
      },
    ]
    expect(component.generateFilterName()).toEqual('Without any tag')

    component.filterRules = [
      {
        rule_type: FILTER_CUSTOM_FIELDS_QUERY,
        value: '["AND",[["42","exists","true"],["43","exists","true"]]]',
      },
    ]
    expect(component.generateFilterName()).toEqual(`Custom fields query`)

    component.filterRules = [
      {
        rule_type: FILTER_TITLE,
        value: 'foo',
      },
    ]
    expect(component.generateFilterName()).toEqual('Title: foo')

    component.filterRules = [
      {
        rule_type: FILTER_ASN,
        value: '1234',
      },
    ]
    expect(component.generateFilterName()).toEqual('ASN: 1234')

    component.filterRules = [
      {
        rule_type: FILTER_OWNER,
        value: '1',
      },
    ]
    expect(component.generateFilterName()).toEqual('Owner: 1')

    component.filterRules = [
      {
        rule_type: FILTER_OWNER_DOES_NOT_INCLUDE,
        value: '1',
      },
    ]
    expect(component.generateFilterName()).toEqual('Owner not in: 1')

    component.filterRules = [
      {
        rule_type: FILTER_OWNER_ISNULL,
        value: 'true',
      },
    ]
    expect(component.generateFilterName()).toEqual('Without an owner')
    component.filterRules = [
      {
        rule_type: FILTER_HAS_TAGS_ANY,
        value: '2',
      },
      {
        rule_type: FILTER_HAS_TAGS_ANY,
        value: '3',
      },
    ]
    expect(component.generateFilterName()).toEqual('')
  })

  it('should support resetting filter rules', () => {
    const rules = [
      {
        rule_type: FILTER_HAS_TAGS_ANY,
        value: '2',
      },
      {
        rule_type: FILTER_HAS_TAGS_ANY,
        value: '3',
      },
    ]
    component.unmodifiedFilterRules = rules
    component.filterRules = [
      {
        rule_type: FILTER_HAS_TAGS_ANY,
        value: '2',
      },
      {
        rule_type: FILTER_DOES_NOT_HAVE_TAG,
        value: '3',
      },
    ]
    component.resetSelected()
    expect(component.filterRules).toEqual(rules)
  })

  it('should support resetting text field', () => {
    component.textFilter = 'foo'
    component.resetTextField()
    expect(component.textFilter).toEqual('')
  })

  it('should support Enter / Esc key on text field', () => {
    component.textFilterInput.nativeElement.value = 'foo'
    component.textFilterInput.nativeElement.dispatchEvent(
      new KeyboardEvent('keyup', { key: 'Enter' })
    )
    expect(component.textFilter).toEqual('foo')
    component.textFilterInput.nativeElement.value = 'foo bar'
    component.textFilterInput.nativeElement.dispatchEvent(
      new KeyboardEvent('keyup', { key: 'Escape' })
    )
    expect(component.textFilter).toEqual('')
    const blurSpy = jest.spyOn(component.textFilterInput.nativeElement, 'blur')
    component.textFilterInput.nativeElement.dispatchEvent(
      new KeyboardEvent('keyup', { key: 'Escape' })
    )
    expect(blurSpy).toHaveBeenCalled()
  })

  it('should adjust text filter targets if more like search', () => {
    const TEXT_FILTER_TARGET_FULLTEXT_MORELIKE = 'fulltext-morelike' // private const
    component.textFilterTarget = TEXT_FILTER_TARGET_FULLTEXT_MORELIKE
    expect(component.textFilterTargets).toContainEqual({
      id: TEXT_FILTER_TARGET_FULLTEXT_MORELIKE,
      name: $localize`More like`,
    })
  })

  it('should call autocomplete endpoint on input', fakeAsync(() => {
    component.textFilterTarget = 'fulltext-query' // TEXT_FILTER_TARGET_FULLTEXT_QUERY
    const autocompleteSpy = jest.spyOn(searchService, 'autocomplete')
    component.searchAutoComplete(of('hello')).subscribe()
    tick(250)
    expect(autocompleteSpy).toHaveBeenCalled()

    component.searchAutoComplete(of('hello world 1')).subscribe()
    tick(250)
    expect(autocompleteSpy).toHaveBeenCalled()
  }))

  it('should handle autocomplete backend failure gracefully', fakeAsync(() => {
    component.textFilterTarget = 'fulltext-query' // TEXT_FILTER_TARGET_FULLTEXT_QUERY
    const serviceAutocompleteSpy = jest.spyOn(searchService, 'autocomplete')
    serviceAutocompleteSpy.mockReturnValue(
      throwError(() => new Error('autcomplete failed'))
    )
    // serviceAutocompleteSpy.mockReturnValue(of([' world']))
    let result
    component.searchAutoComplete(of('hello')).subscribe((res) => {
      result = res
    })
    tick(250)
    expect(serviceAutocompleteSpy).toHaveBeenCalled()
    expect(result).toEqual([])
  }))

  it('should support choosing a autocomplete item', () => {
    expect(component.textFilter).toBeNull()
    component.itemSelected({ item: 'hello', preventDefault: () => true })
    expect(component.textFilter).toEqual('hello ')
    component.itemSelected({ item: 'world', preventDefault: () => true })
    expect(component.textFilter).toEqual('hello world ')
  })
})
