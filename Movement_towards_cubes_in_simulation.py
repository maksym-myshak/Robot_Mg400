import rclpy
import math
from rclpy.node import Node
from sensor_msgs.msg import JointState

class Mg400OptimizedSequence(Node):
    def __init__(self):
        super().__init__('mg400_optimized_node')
        
        # Створюємо видавця, який надсилає позиції суглобів у топік /joint_states
        self.publisher_ = self.create_publisher(JointState, '/joint_states', 10)
        # Таймер 0.01 сек = частота 100 Гц для високої плавності
        self.timer = self.create_timer(0.01, self.timer_callback)
        
        # Імена суглобів відповідно до URDF моделі Dobot MG400
        self.joint_names = [
            'mg400_j1', 'mg400_j2_1', 'mg400_j2_2', 
            'mg400_j3_1', 'mg400_j3_2', 'mg400_j4_1', 
            'mg400_j4_2', 'mg400_j5'
        ]
        
        # Цільові точки
        self.home = [0.0] * 8
        self.red = [0.0, 1.44705, 1.44705, -0.00017, -1.44705, -1.44688, 1.44688, 0.0]
        self.green = [1.55264, 1.44705, 1.44705, 0.32882, -1.44705, -1.77587, 1.77587, 0.0]
        self.blue = [-2.35130, 1.48352, 1.48352, -0.22270, -1.48352, -1.26082, 1.26082, 0.63669]
        
        # Точки зависання
        self.red_h = [self.red[0]] + [0.0] * 7
        self.green_h = [self.green[0]] + [0.0] * 7
        self.blue_h = [self.blue[0]] + [0.0] * 7
        
        # Послідовний маршрут
        self.waypoints = [
            self.home,
            self.red_h, self.red, self.red_h,
            self.green_h, self.green, self.green_h,
            self.blue_h, self.blue, self.blue_h,
            self.home
        ]
        
        self.current_wp_idx = 0       # Індекс поточної цілі
        self.current_angles = list(self.home)
        self.start_angles = list(self.home)
        
        self.step = 0                 # Лічильник кроків всередині одного руху
        self.max_steps = 150          # Тривалість рух
        self.pause_steps = 40         # Тривалість паузи
        
        self.state = 'MOVING'         # Машина станів
        self.pause_counter = 0
        
        self.get_logger().info('Програму запущено. Початок виконання маршруту...')

    def timer_callback(self):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = self.joint_names
        
        # Перевірка: чи не закінчився маршрут
        if self.current_wp_idx >= len(self.waypoints) - 1:
            msg.position = self.waypoints[-1]
            self.publisher_.publish(msg)
            return
            
        target = self.waypoints[self.current_wp_idx + 1]
        
        if self.state == 'MOVING':
            if self.step <= self.max_steps:
                # S-крива плавне прискорення та гальмування через cos
                progress = (1 - math.cos(math.pi * self.step / self.max_steps)) / 2
                
                # Обчислюємо нову позицію для кожного суглоба
                new_positions = []
                for i in range(8):
                    dist = target[i] - self.start_angles[i]
                    new_positions.append(self.start_angles[i] + dist * progress)
                
                self.current_angles = new_positions
                msg.position = self.current_angles
                self.publisher_.publish(msg)
                self.step += 1
            else:
                # Рух закінчено, переходимо до паузи
                self.state = 'PAUSED'
                self.pause_counter = 0
                self.current_wp_idx += 1
                    
        elif self.state == 'PAUSED':
            # Під час паузи просто утримуємо поточну позицію
            msg.position = self.waypoints[self.current_wp_idx]
            self.publisher_.publish(msg)
            self.pause_counter += 1
            
            if self.pause_counter >= self.pause_steps:
                # Пауза закінчена, готуємося до наступного руху
                self.state = 'MOVING'
                self.step = 0
                self.start_angles = list(self.current_angles)

def main(args=None):
    rclpy.init(args=args)
    node = Mg400OptimizedSequence()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()