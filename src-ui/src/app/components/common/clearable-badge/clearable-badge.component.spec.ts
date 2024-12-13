import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { ClearableBadgeComponent } from './clearable-badge.component'

describe('ClearableBadgeComponent', () => {
  let component: ClearableBadgeComponent
  let fixture: ComponentFixture<ClearableBadgeComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [ClearableBadgeComponent],
      imports: [NgxBootstrapIconsModule.pick(allIcons)],
    }).compileComponents()

    fixture = TestBed.createComponent(ClearableBadgeComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should support selected', () => {
    component.selected = true
    expect(component.active).toBeTruthy()
  })

  it('should support numbered', () => {
    component.number = 3
    fixture.detectChanges()
    expect(component.active).toBeTruthy()
    expect((fixture.nativeElement as HTMLDivElement).textContent).toContain('3')
  })

  it('should support selected', () => {
    let clearedResult
    component.selected = true
    fixture.detectChanges()
    component.cleared.subscribe((clear) => {
      clearedResult = clear
    })
    fixture.nativeElement
      .querySelectorAll('button')[0]
      .dispatchEvent(new MouseEvent('click'))
    expect(clearedResult).toBeTruthy()
  })
})
