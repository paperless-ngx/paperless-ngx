import { ComponentFixture, TestBed } from '@angular/core/testing'

import { LoadingDialogComponent } from './loading-dialog.component'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'

describe('LoadingDialogComponent', () => {
  let component: LoadingDialogComponent
  let fixture: ComponentFixture<LoadingDialogComponent>

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [LoadingDialogComponent],
      providers: [NgbActiveModal],
    })
    fixture = TestBed.createComponent(LoadingDialogComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should display verb, count and total', () => {
    component.verb = 'Loading item'
    component.current = 3
    component.total = 10
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      'Loading item 3 of 10'
    )
  })
})
