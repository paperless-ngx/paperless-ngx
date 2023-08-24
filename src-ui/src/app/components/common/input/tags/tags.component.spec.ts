import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import {
  FormsModule,
  ReactiveFormsModule,
  NG_VALUE_ACCESSOR,
} from '@angular/forms'
import { TagsComponent } from './tags.component'
import { PaperlessTag } from 'src/app/data/paperless-tag'
import {
  DEFAULT_MATCHING_ALGORITHM,
  MATCH_ALL,
} from 'src/app/data/matching-model'
import { NgSelectComponent, NgSelectModule } from '@ng-select/ng-select'
import { RouterTestingModule } from '@angular/router/testing'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { of } from 'rxjs'
import { TagService } from 'src/app/services/rest/tag.service'
import {
  NgbAccordionModule,
  NgbModal,
  NgbModalModule,
  NgbModalRef,
  NgbPopoverModule,
} from '@ng-bootstrap/ng-bootstrap'
import { TagEditDialogComponent } from '../../edit-dialog/tag-edit-dialog/tag-edit-dialog.component'
import { CheckComponent } from '../check/check.component'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { TextComponent } from '../text/text.component'
import { ColorComponent } from '../color/color.component'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsFormComponent } from '../permissions/permissions-form/permissions-form.component'
import { SelectComponent } from '../select/select.component'
import { ColorSliderModule } from 'ngx-color/slider'
import { By } from '@angular/platform-browser'

const tags: PaperlessTag[] = [
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
  let input: HTMLInputElement
  let modalService: NgbModal

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
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
      ],
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgSelectModule,
        RouterTestingModule,
        HttpClientTestingModule,
        NgbModalModule,
        NgbAccordionModule,
        NgbPopoverModule,
      ],
    }).compileComponents()

    modalService = TestBed.inject(NgbModal)
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
    let activeInstances: NgbModalRef[]
    modalService.activeInstances.subscribe((v) => (activeInstances = v))
    component.select.searchTerm = 'foobar'
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
    component.removeTag(new PointerEvent('point'), 2)
    expect(component.value).toEqual([1])

    component.disabled = true
    component.removeTag(new PointerEvent('point'), 1)
    expect(component.value).toEqual([1])
  })

  it('should get tags', () => {
    component.tags = null
    expect(component.getTag(2)).toBeNull()
    component.tags = tags
    expect(component.getTag(2)).toEqual(tags[1])
    expect(component.getTag(4)).toBeUndefined()
  })
})
