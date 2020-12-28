import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ToggleableDropdownButtonComponent } from './toggleable-dropdown-button.component';

describe('ToggleableDropdownButtonComponent', () => {
  let component: ToggleableDropdownButtonComponent;
  let fixture: ComponentFixture<ToggleableDropdownButtonComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ ToggleableDropdownButtonComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(ToggleableDropdownButtonComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
