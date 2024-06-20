import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ViewallForderComponent } from './viewall-forder.component';

describe('ViewallForderComponent', () => {
  let component: ViewallForderComponent;
  let fixture: ComponentFixture<ViewallForderComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ViewallForderComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(ViewallForderComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
