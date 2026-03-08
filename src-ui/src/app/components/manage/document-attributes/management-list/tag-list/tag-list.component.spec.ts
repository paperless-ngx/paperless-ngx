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
import { TagService } from 'src/app/services/rest/tag.service'
import { PageHeaderComponent } from '../../../../common/page-header/page-header.component'
import { TagListComponent } from './tag-list.component'

describe('TagListComponent', () => {
  let component: TagListComponent
  let fixture: ComponentFixture<TagListComponent>
  let tagService: TagService
  let listFilteredSpy: jest.SpyInstance

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NgbPaginationModule,
        FormsModule,
        ReactiveFormsModule,
        NgxBootstrapIconsModule.pick(allIcons),
        TagListComponent,
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

    tagService = TestBed.inject(TagService)
    listFilteredSpy = jest.spyOn(tagService, 'listFiltered').mockReturnValue(
      of({
        count: 3,
        all: [1, 2, 3],
        results: [
          {
            id: 1,
            name: 'Tag1',
          },
          {
            id: 2,
            name: 'Tag2',
          },
          {
            id: 3,
            name: 'Tag3',
          },
        ],
      })
    )
    fixture = TestBed.createComponent(TagListComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  // Tests are included in management-list.component.spec.ts

  it('should use correct delete message', () => {
    expect(component.getDeleteMessage({ id: 1, name: 'Tag1' })).toEqual(
      'Do you really want to delete the tag "Tag1"?'
    )
  })

  it('should omit matching children from top level when their parent is present', () => {
    const tags = [
      {
        id: 1,
        name: 'Tag1',
        parent: null,
        children: [{ id: 2, name: 'Tag2', parent: 1 }],
      },
      { id: 2, name: 'Tag2', parent: 1 },
      { id: 3, name: 'Tag3', parent: null },
    ]
    component['_nameFilter'] = null // Simulate empty name filter
    const filtered = component.filterData(tags as any)
    expect(filtered.length).toBe(2)
    expect(filtered.find((t) => t.id === 2)).toBeUndefined()

    component['_nameFilter'] = 'Tag2' // Simulate non-empty name filter
    const filteredWithName = component.filterData(tags as any)
    expect(filteredWithName.length).toBe(2)
    expect(filteredWithName.find((t) => t.id === 2)).toBeUndefined()
    expect(
      filteredWithName
        .find((t) => t.id === 1)
        ?.children?.some((c) => c.id === 2)
    ).toBe(true)
  })

  it('should request only parent tags when no name filter is applied', () => {
    expect(tagService.listFiltered).toHaveBeenCalledWith(
      1,
      25,
      undefined,
      undefined,
      undefined,
      true,
      { is_root: true }
    )
  })

  it('should include child tags when a name filter is applied', () => {
    listFilteredSpy.mockClear()
    component['_nameFilter'] = 'Tag'
    component.reloadData()
    expect(tagService.listFiltered).toHaveBeenCalledWith(
      1,
      25,
      undefined,
      undefined,
      'Tag',
      true,
      null
    )
  })

  it('should include child tags when selecting all', () => {
    const parent = {
      id: 10,
      name: 'Parent',
      children: [
        {
          id: 11,
          name: 'Child',
        },
      ],
    }

    component.data = [parent as any]
    component.selectPage()

    expect(component.selectedObjects.has(10)).toBe(true)
    expect(component.selectedObjects.has(11)).toBe(true)

    component.clearSelection()
    expect(component.selectedObjects.size).toBe(0)
  })
})
