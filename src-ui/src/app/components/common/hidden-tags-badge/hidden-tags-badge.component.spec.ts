import { ComponentFixture, TestBed } from '@angular/core/testing'
import { HiddenTagsBadgeComponent } from './hidden-tags-badge.component'

describe('HiddenTagsBadgeComponent', () => {
  let fixture: ComponentFixture<HiddenTagsBadgeComponent>

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HiddenTagsBadgeComponent],
    })
    fixture = TestBed.createComponent(HiddenTagsBadgeComponent)
    fixture.componentRef.setInput('count', 3)
    fixture.detectChanges()
  })

  it('should show the hidden tag count', () => {
    expect(fixture.nativeElement.textContent).toContain('3 hidden')
  })
})
