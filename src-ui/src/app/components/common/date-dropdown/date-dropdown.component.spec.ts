import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DateDropdownComponent } from './date-dropdown.component';

describe('DateDropdownComponent', () => {
  let component: DateDropdownComponent;
  let fixture: ComponentFixture<DateDropdownComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ DateDropdownComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(DateDropdownComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
