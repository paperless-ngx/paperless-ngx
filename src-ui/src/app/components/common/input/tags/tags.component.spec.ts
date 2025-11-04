import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { RouterTestingModule } from '@angular/router/testing'
import {
  NgbAccordionModule,
  NgbModal,
  NgbModalModule,
  NgbModalRef,
  NgbPopoverModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of } from 'rxjs'
import {
  DEFAULT_MATCHING_ALGORITHM,
  MATCH_ALL,
} from 'src/app/data/matching-model'
import { Tag } from 'src/app/data/tag'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { TagService } from 'src/app/services/rest/tag.service'
import { SettingsService } from 'src/app/services/settings.service'
import { TagEditDialogComponent } from '../../edit-dialog/tag-edit-dialog/tag-edit-dialog.component'
import { CheckComponent } from '../check/check.component'
import { ColorComponent } from '../color/color.component'
import { PermissionsFormComponent } from '../permissions/permissions-form/permissions-form.component'
import { SelectComponent } from '../select/select.component'
import { TextComponent } from '../text/text.component'
import { TagsComponent } from './tags.component'

const tags: Tag[] = [
  {
    id: 1,
    name: 'Tag1',
    is_inbox_tag: false,
    matching_algorithm: DEFAULT_MATCHING_ALGORITHM,
  },
  {
    id: 2,
    name: 'Tag2',
    is_inbox_tag: true,
    matching_algorithm: MATCH_ALL,
    match: 'str',
  },
  {
    id: 10,
    name: 'Tag10',
    is_inbox_tag: false,
    matching_algorithm: DEFAULT_MATCHING_ALGORITHM,
  },
]

describe('TagsComponent', () => {
  let component: TagsComponent
  let fixture: ComponentFixture<TagsComponent>
  let modalService: NgbModal
  let settingsService: SettingsService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgSelectModule,
        RouterTestingModule,
        NgbModalModule,
        NgbAccordionModule,
        NgbPopoverModule,
        NgxBootstrapIconsModule.pick(allIcons),
        TagsComponent,
        TagEditDialogComponent,
        TextComponent,
        ColorComponent,
        IfOwnerDirective,
        SelectComponent,
        TextComponent,
        PermissionsFormComponent,
        ColorComponent,
        CheckComponent,
      ],
      providers: [
        {
          provide: TagService,
          useValue: {
            listAll: () =>
              of({
                results: tags,
              }),
            create: () =>
              of({
                name: 'bar',
                id: 99,
                color: '#fff000',
              }),
          },
        },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    modalService = TestBed.inject(NgbModal)
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser = { id: 1 }
    fixture = TestBed.createComponent(TagsComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()

    window.PointerEvent = MouseEvent as any
  })

  it('should support suggestions', () => {
    expect(component.value).toHaveLength(0)
    component.value = []
    component.tags = tags
    component.suggestions = [1, 2]
    fixture.detectChanges()
    const suggestionAnchor: HTMLAnchorElement =
      fixture.nativeElement.querySelector('a')
    suggestionAnchor.click()
    expect(component.value).toEqual([1])
  })

  it('should support create new and open a modal', () => {
    let activeInstances: NgbModalRef[]
    modalService.activeInstances.subscribe((v) => (activeInstances = v))
    component.createTag('foo')
    expect(modalService.hasOpenModals()).toBeTruthy()
    expect(activeInstances[0].componentInstance.object.name).toEqual('foo')
  })

  it('should support create new using last search term and open a modal', () => {
    settingsService.currentUser = { id: 1 }
    let activeInstances: NgbModalRef[]
    modalService.activeInstances.subscribe((v) => (activeInstances = v))
    component.select.filter('foobar')
    component.createTag()
    expect(modalService.hasOpenModals()).toBeTruthy()
    expect(activeInstances[0].componentInstance.object.name).toEqual('foobar')
    const editDialog = activeInstances[0]
      .componentInstance as TagEditDialogComponent
    editDialog.save() // create is mocked
    fixture.detectChanges()
    fixture.whenStable().then(() => {
      expect(fixture.debugElement.nativeElement.textContent).toContain('foobar')
    })
  })

  it('support remove tags', () => {
    component.tags = tags
    component.value = [1, 2]
    component.removeTag(2)
    expect(component.value).toEqual([1])

    component.disabled = true
    component.removeTag(1)
    expect(component.value).toEqual([1])
  })

  it('should get tags', () => {
    component.tags = null
    expect(component.getTag(2)).toBeNull()
    component.tags = tags
    expect(component.getTag(2)).toEqual(tags[1])
    expect(component.getTag(4)).toBeUndefined()
  })

  it('should emit filtered documents', () => {
    component.value = [10]
    component.tags = tags
    const emitSpy = jest.spyOn(component.filterDocuments, 'emit')
    component.onFilterDocuments()
    expect(emitSpy).toHaveBeenCalledWith([tags[2]])
  })

  it('should remove all descendants from selection', () => {
    const c: Tag = { id: 4, name: 'c' }
    const b: Tag = { id: 3, name: 'b', children: [c] }
    const a: Tag = { id: 2, name: 'a' }
    const root: Tag = { id: 1, name: 'root', children: [a, b] }

    const inputIDs = [2, 3, 4, 99]
    const result = (component as any).removeChildren(inputIDs, root)
    expect(result).toEqual([99])
  })

  it('should append all parents recursively', () => {
    const root: Tag = { id: 1, name: 'root' }
    const mid: Tag = { id: 2, name: 'mid', parent: 1 }
    const leaf: Tag = { id: 3, name: 'leaf', parent: 2 }
    component.tags = [root, mid, leaf]

    component.value = []
    component.onAdd(leaf)
    expect(component.value).toEqual([2, 1])

    // Calling onAdd on a root should not change value
    component.onAdd(root)
    expect(component.value).toEqual([2, 1])
  })

  it('should return ancestors from root to parent using getParentChain', () => {
    const root: Tag = { id: 1, name: 'root' }
    const mid: Tag = { id: 2, name: 'mid', parent: 1 }
    const leaf: Tag = { id: 3, name: 'leaf', parent: 2 }
    component.tags = [root, mid, leaf]

    expect(component.getParentChain(3).map((t) => t.id)).toEqual([1, 2])
    expect(component.getParentChain(2).map((t) => t.id)).toEqual([1])
    expect(component.getParentChain(1).map((t) => t.id)).toEqual([])
    // Non-existent id
    expect(component.getParentChain(999).map((t) => t.id)).toEqual([])
  })

  it('should handle cyclic parents via guard in getParentChain', () => {
    const one: Tag = { id: 1, name: 'one', parent: 2 }
    const two: Tag = { id: 2, name: 'two', parent: 1 }
    component.tags = [one, two]

    const chain = component.getParentChain(1)
    // Guard avoids infinite loop; chain contains both nodes once
    expect(chain.map((t) => t.id)).toEqual([1, 2])
  })

  it('should stop when parent does not exist in getParentChain', () => {
    const lone: Tag = { id: 5, name: 'lone', parent: 999 }
    component.tags = [lone]
    expect(component.getParentChain(5)).toEqual([])
  })
})
