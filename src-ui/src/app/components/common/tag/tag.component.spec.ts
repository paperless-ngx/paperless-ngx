import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { of } from 'rxjs'
import { Tag } from 'src/app/data/tag'
import { PermissionsService } from 'src/app/services/permissions.service'
import { TagService } from 'src/app/services/rest/tag.service'
import { SettingsService } from 'src/app/services/settings.service'
import { TagComponent } from './tag.component'

const tag: Tag = {
  id: 1,
  color: '#ff0000',
  name: 'Tag1',
}

describe('TagComponent', () => {
  let component: TagComponent
  let fixture: ComponentFixture<TagComponent>
  let permissionsService: PermissionsService
  let tagService: TagService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
      imports: [TagComponent],
    }).compileComponents()

    permissionsService = TestBed.inject(PermissionsService)
    tagService = TestBed.inject(TagService)
    fixture = TestBed.createComponent(TagComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should create tag with background color', () => {
    component.tag.set(tag)
    fixture.detectChanges()
    expect(
      fixture.debugElement.query(By.css('span')).nativeElement.style
        .backgroundColor
    ).toEqual('rgb(255, 0, 0)')
  })

  it('should handle private tags', () => {
    expect(
      fixture.debugElement.query(By.css('span')).nativeElement.textContent
    ).toEqual('Private')
  })

  it('should support clickable option', () => {
    component.tag.set(tag)
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('a.badge'))).toBeNull()
    fixture.componentRef.setInput('clickable', true)
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('a.badge'))).not.toBeNull()
  })

  it('should support retrieving tag by ID', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    const getCachedSpy = jest.spyOn(tagService, 'getCached')
    getCachedSpy.mockReturnValue(of(tag))
    fixture.componentRef.setInput('tagID', 1)
    fixture.detectChanges()
    expect(getCachedSpy).toHaveBeenCalledWith(1)
    expect(component.tag()).toEqual(tag)
  })
  describe('split badge', () => {
    const root: Tag = { id: 1, name: 'Root', color: '#000000' }
    const mid: Tag = { id: 2, name: 'Mid', color: '#111111', parent: 1 }
    const leaf: Tag = { id: 3, name: 'Leaf', color: '#222222', parent: 2 }

    const segments = (): HTMLElement[] =>
      fixture.debugElement
        .queryAll(By.css('.split-pill > .badge'))
        .map((d) => d.nativeElement)

    beforeEach(() => {
      jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
      jest.spyOn(tagService, 'getCached').mockReturnValue(of(leaf))
      jest
        .spyOn(tagService, 'listAll')
        .mockReturnValue(
          of({ count: 3, all: [1, 2, 3], results: [root, mid, leaf] })
        )
      fixture.componentRef.setInput('tagID', 3)
      fixture.componentRef.setInput('split', true)
      fixture.detectChanges()
    })

    it('should render ancestors as segments with the full path as title', () => {
      expect(segments().map((s) => s.textContent.trim())).toEqual([
        'Root',
        'Mid',
        'Leaf',
      ])
      expect(
        fixture.debugElement.query(By.css('.split-pill')).nativeElement.title
      ).toEqual('Root › Mid › Leaf')
    })

    it('should render a plain badge when the setting is off', () => {
      jest.spyOn(TestBed.inject(SettingsService), 'get').mockReturnValue(false)
      fixture.componentRef.setInput('split', false)
      fixture.detectChanges()
      fixture.componentRef.setInput('split', true)
      fixture.detectChanges()
      expect(fixture.debugElement.query(By.css('.split-pill'))).toBeNull()
      expect(component.ancestorSegments).toEqual([])
    })

    it('should emit the ancestor id when an ancestor segment is clicked', () => {
      const emitSpy = jest.spyOn(component.parentClick, 'emit')
      const event = new MouseEvent('click', { bubbles: true })
      const stopSpy = jest.spyOn(event, 'stopImmediatePropagation')
      segments()[1].dispatchEvent(event)
      expect(emitSpy).toHaveBeenCalledWith(2)
      expect(stopSpy).toHaveBeenCalled()
    })

    it('should focus the hovered segment and animate width changes', () => {
      const [rootSeg, midSeg, leafSeg] = segments()
      const pill = rootSeg.parentElement
      // before / after widths per segment, as measured by setFocus
      const widths = new Map<HTMLElement, number[]>([
        [rootSeg, [20, 4]],
        [midSeg, [20, 60]],
        [leafSeg, [40, 40]],
      ])
      const animate = jest.fn()
      for (const [seg, [before, after]] of widths) {
        seg.getAnimations = jest.fn(() => [])
        seg.animate = animate
        jest
          .spyOn(seg, 'getBoundingClientRect')
          .mockReturnValueOnce({ width: before } as DOMRect)
          .mockReturnValueOnce({ width: after } as DOMRect)
      }

      midSeg.dispatchEvent(new MouseEvent('mouseenter'))
      expect(midSeg.classList).toContain('focused')
      expect(rootSeg.classList).not.toContain('focused')
      // only the segments whose width changed are animated
      expect(animate).toHaveBeenCalledTimes(2)

      pill.dispatchEvent(new MouseEvent('mouseleave'))
      expect(segments().some((s) => s.classList.contains('focused'))).toBe(
        false
      )
    })
  })
})
