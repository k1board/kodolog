"""Пример работы с логической ошибкой: код выглядит прилично, но падает на тестах."""


def fizzbuzz(n: int) -> list[str]:
    """Классический fizzbuzz для чисел от 1 до n включительно."""
    answer = []
    for i in range(1, n):  # ошибка: забыли включить n (нужно range(1, n + 1))
        if i % 15 == 0:
            answer.append("FizzBuzz")
        elif i % 3 == 0:
            answer.append("Fizz")
        elif i % 5 == 0:
            answer.append("Buzz")
        else:
            answer.append(str(i))
    return answer
