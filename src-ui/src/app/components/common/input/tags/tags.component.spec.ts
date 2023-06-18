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
import { NgSelectModule } from '@ng-select/ng-select'
import { RouterTestingModule } from '@angular/router/testing'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { of } from 'rxjs'
import { TagService } from 'src/app/services/rest/tag.service'
import {
  NgbModal,
  NgbModalModule,
  NgbModalRef,
} from '@ng-bootstrap/ng-bootstrap'

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
      declarations: [TagsComponent],
      providers: [
        {
          provide: TagService,
          useValue: {
            listAll: () => of(tags),
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
    expect(component.value).toBeUndefined()
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
    component.onSearch({ term: 'bar' })
    component.createTag()
    expect(modalService.hasOpenModals()).toBeTruthy()
    expect(activeInstances[0].componentInstance.object.name).toEqual('bar')
  })

  it('should clear search term on blur after delay', fakeAsync(() => {
    const clearSpy = jest.spyOn(component, 'clearLastSearchTerm')
    component.onBlur()
    tick(3000)
    expect(clearSpy).toHaveBeenCalled()
  }))

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
    expect(component.getTag(2)).toBeNull()
    component.tags = tags
    expect(component.getTag(2)).toEqual(tags[1])
    expect(component.getTag(4)).toBeUndefined()
  })
})
