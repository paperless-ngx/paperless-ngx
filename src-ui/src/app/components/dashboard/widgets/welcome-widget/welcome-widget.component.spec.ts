import { ComponentFixture, TestBed } from '@angular/core/testing';

import { WelcomeWidgetComponent } from './welcome-widget.component';

describe('WelcomeWidgetComponent', () => {
  let component: WelcomeWidgetComponent;
  let fixture: ComponentFixture<WelcomeWidgetComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ WelcomeWidgetComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(WelcomeWidgetComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
